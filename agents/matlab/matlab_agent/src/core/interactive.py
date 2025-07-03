"""Interactive simulation core (MATLAB side)

Revision: r6 – **single-thread event loop**
-----------------------------------------
* Rimosso l’uso di `process_data_events` da un thread separato: Pika
  `BlockingConnection` non è thread-safe e provocava `StreamLostError`.
* Ora un **unico loop** gestisce contemporaneamente:
  • pompaggio di RabbitMQ (input) tramite `connection.process_data_events()`
  • inoltro di frame a MATLAB via TCP
  • lettura di risposte da MATLAB e forward al broker
* Eliminati i duplicati della funzione `_push_frame` e mantenuto
  `handle_interactive_input` come alias.
* Architettura più semplice, nessun accesso concorrente all’oggetto
  `BlockingConnection`.
"""

import json
import time
import yaml
import subprocess
from pathlib import Path
from queue import Queue, Empty
from typing import Any, Dict, Optional
from functools import partial
import socket
from select import select
import psutil

from ..comm.interfaces import IMessageBroker
from ..utils.create_response import create_response
from ..utils.logger import get_logger
from ..utils.performance_monitor import PerformanceMonitor

logger = get_logger()

# ──────────────────────────────────────────────────────────────────────────────
# RabbitMQ → Queue callback (kept for legacy import)
# ──────────────────────────────────────────────────────────────────────────────

def _push_frame(ch, method, properties, body, q: Queue) -> None:
    try:
        q.put(yaml.safe_load(body))
    except Exception as exc:
        logger.error("[INTERACTIVE] Bad frame: %s", exc)

handle_interactive_input = _push_frame  # backward-compat

# ──────────────────────────────────────────────────────────────────────────────
# TCP helper (JSON-lines)
# ──────────────────────────────────────────────────────────────────────────────

class _TcpServer:
    def __init__(self, host: str, port: int) -> None:
        self.addr = (host, port)
        self._srv: Optional[socket.socket] = None
        self._conn: Optional[socket.socket] = None
        self.matlab_proc: Optional[subprocess.Popen] = None  # solo per OUT

    def start(self) -> None:
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(self.addr)
        self._srv.listen()

    def accept_blocking(self) -> None:
        self._conn, _ = self._srv.accept()
        self._conn.setblocking(False)

    def send(self, data: dict) -> None:
        if self._conn:
            self._conn.sendall((json.dumps(data) + "\n").encode())

    def recv_all(self) -> list[dict]:
        if not self._conn or not select([self._conn], [], [], 0)[0]:
            return []
        chunk = self._conn.recv(4096)
        return [json.loads(line.decode()) for line in chunk.split(b"\n") if line.strip()]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
        if self._srv:
            self._srv.close()
        if self.matlab_proc and self.matlab_proc.poll() is None:
            self.matlab_proc.terminate()
            self.matlab_proc.wait(timeout=5)

# ──────────────────────────────────────────────────────────────────────────────
# Controller
# ──────────────────────────────────────────────────────────────────────────────

class MatlabInteractiveController:
    def __init__(
        self,
        path: str,
        file: str,
        source: str,
        broker: IMessageBroker,
        tmpl: Dict[str, Any],
        tcp_cfg: Dict[str, Any],
        bridge_meta: str,
        request_id: str,
        agent_id: str = "agent",
    ) -> None:
        self.sim_path = Path(path).resolve()
        self.sim_file = file
        if not (self.sim_path / self.sim_file).exists():
            raise FileNotFoundError(self.sim_file)

        self.source = source
        self.broker = broker
        self.tmpl = tmpl
        self.bridge_meta = bridge_meta
        self.request_id = request_id
        self.agent_id = agent_id

        self.out_srv = _TcpServer(tcp_cfg.get("output_host", "localhost"), tcp_cfg.get("output_port", 5678))
        self.in_srv  = _TcpServer(tcp_cfg.get("input_host", "localhost"),  tcp_cfg.get("input_port", 5679))

        self.start_time: Optional[float] = None
        self._seq = 0

    # -------- bootstrap --------
    def _start_matlab(self) -> None:
        cmd = [
            "matlab",
            "-batch",
            f"addpath('{self.sim_path}');port={self.out_srv.addr[1]};cd('{self.sim_path}');run('{self.sim_file}');",
        ]
        self.out_srv.matlab_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def start(self, pm: PerformanceMonitor) -> None:
        self.start_time = time.time()
        self.out_srv.start(); self.in_srv.start()
        self._start_matlab()
        pm.record_matlab_startup_complete()
        self.out_srv.accept_blocking(); self.in_srv.accept_blocking()

    # -------- helpers --------
    def _relay(self, msg: dict) -> None:
        self.broker.send_result(
            self.source,
            create_response(
                "interactive",
                self.sim_file,
                "interactive",
                self.tmpl,
                data=msg,
                sequence=self._seq,
                bridge_meta=self.bridge_meta,
                request_id=self.request_id,
            ),
        )
        self._seq += 1

    # -------- main event loop --------
    def run(self, init_inputs: Dict[str, Any], pm: PerformanceMonitor, msg_dict: Dict[str, Any]) -> None:
        sim = msg_dict["simulation"]
        stream_key = sim["inputs"]["stream_source"].replace("rabbitmq://", "")
        q_in: Queue = Queue()

        ch = self.broker.channel
        qname = f"Q.{self.agent_id}.interactive.{self.request_id}"
        ch.exchange_declare("ex.input.stream", exchange_type="topic", durable=True)
        ch.queue_declare(queue=qname, durable=True)
        ch.queue_bind(exchange="ex.input.stream", queue=qname, routing_key=stream_key)
        ch.basic_consume(queue=qname, on_message_callback=partial(_push_frame, q=q_in), auto_ack=True)

        # handshake
        self.out_srv.send(init_inputs)

        try:
            while True:
                # 1) pompaggio RabbitMQ
                self.broker.connection.process_data_events(time_limit=0)

                # 2) inoltra tutti i frame disponibili a MATLAB
                while True:
                    try:
                        frame = q_in.get_nowait()
                    except Empty:
                        break
                    self.in_srv.send(frame)

                # 3) inoltra tutte le risposte MATLAB → broker
                for resp in self.out_srv.recv_all():
                    self._relay(resp)

                time.sleep(0.01)
        finally:
            pm.record_simulation_complete()
            self.close()

    # -------- cleanup --------
    def close(self) -> None:
        self.out_srv.close(); self.in_srv.close()

    def metadata(self) -> Dict[str, Any]:
        meta = {}
        if self.start_time:
            meta["execution_time"] = time.time() - self.start_time
        meta["memory_usage"] = psutil.Process().memory_info().rss // (1024 * 1024)
        return meta

# ──────────────────────────────────────────────────────────────────────────────
# Public entry
# ──────────────────────────────────────────────────────────────────────────────

def handle_interactive_simulation(
    msg_dict: Dict[str, Any],
    source: str,
    rabbitmq_manager: IMessageBroker,
    path_simulation: str,
    response_templates: Dict[str, Any],
    tcp_settings: Dict[str, Any],
) -> None:
    pm = PerformanceMonitor()
    sim = msg_dict["simulation"]
    pm.start_operation(sim["request_id"])

    ctrl = MatlabInteractiveController(
        path_simulation or sim.get("path"),
        sim["file"],
        source,
        rabbitmq_manager,
        response_templates,
        tcp_settings,
        sim.get("bridge_meta", "unknown"),
        sim["request_id"],
        agent_id=sim.get("simulator", "agent"),
    )
    try:
        ctrl.start(pm)
        ctrl.run(sim.get("inputs", {}), pm, msg_dict)
    except Exception as exc:
        logger.error("[INTERACTIVE] Fatal: %s", exc)
        rabbitmq_manager.send_result(
            source,
            create_response(
                "error",
                sim.get("file", ""),
                "interactive",
                response_templates,
                bridge_meta=sim.get("bridge_meta", "unknown"),
                request_id=sim.get("request_id", "unknown"),
                error={"message": str(exc), "type": "execution_error"},
            ),
        )
    finally:
        pm.complete_operation()
        ctrl.close()