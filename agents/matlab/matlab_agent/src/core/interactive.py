"""Interactive MATLAB simulation bridge."""

from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path
from select import select
from typing import Any, Dict, Optional

import psutil
import yaml

from ..comm.interfaces import IMessageBroker
from ..utils.create_response import create_response
from ..utils.logger import get_logger
from ..utils.performance_monitor import PerformanceMonitor

logger = get_logger()


def _parse_frame(body: bytes) -> Dict[str, Any]:
    """Decode a YAML frame received from RabbitMQ."""
    try:
        return yaml.safe_load(body)
    except Exception as exc:  # pragma: no cover - logging only
        logger.error("[INTERACTIVE] Bad frame: %s", exc)
        return {}


class _TcpServer:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._srv: Optional[socket.socket] = None
        self._conn: Optional[socket.socket] = None
        self._buffer = b""
        self.matlab_proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((self.host, self.port))
        self._srv.listen()

    def accept(self) -> None:
        if not self._srv:
            raise RuntimeError("Server not started")
        ready = select([self._srv], [], [], 60)
        if ready[0]:
            self._conn, _ = self._srv.accept()
            self._conn.setblocking(False)
        else:
            logger.error(
                "[INTERACTIVE] Timeout waiting for client connection.")
            raise TimeoutError("No client connection received in time.")

    def send(self, data: Dict[str, Any]) -> None:
        if self._conn:
            payload = json.dumps(data).encode() + b"\n"
            self._conn.sendall(payload)

    def recv_all(self) -> list[Dict[str, Any]]:
        if not self._conn or not select([self._conn], [], [], 0)[0]:
            return []

        self._buffer += self._conn.recv(4096)
        lines = self._buffer.split(b"\n")
        self._buffer = lines[-1]
        messages: list[Dict[str, Any]] = []
        for line in lines[:-1]:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line.decode()))
            except json.JSONDecodeError as exc:  # pragma: no cover - logging only
                logger.error("[INTERACTIVE] Invalid JSON: %s", exc)
        return messages

    def close(self) -> None:
        if self._conn:
            self._conn.close()
        if self._srv:
            self._srv.close()
        if self.matlab_proc and self.matlab_proc.poll() is None:
            self.matlab_proc.terminate()
            try:
                self.matlab_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - best effort
                self.matlab_proc.kill()


class MatlabInteractiveController:
    def __init__(
        self,
        path: str,
        file: str,
        source: str,
        broker: IMessageBroker,
        templates: Dict[str, Any],
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
        self.templates = templates
        self.bridge_meta = bridge_meta
        self.request_id = request_id
        self.agent_id = agent_id

        self.out_srv = _TcpServer(
            tcp_cfg.get("host", "localhost"),
            tcp_cfg.get("output_port", 5678),
        )
        self.in_srv = _TcpServer(
            tcp_cfg.get("host", "localhost"),
            tcp_cfg.get("input_port", 5679),
        )

        self.start_time: Optional[float] = None
        self.sequence = 0

    # ------------------------------------------------------------------
    def _start_matlab(self) -> None:
        cmd = [
            "matlab",
            "-batch",
            f"addpath('{
                self.sim_path}');cd('{
                self.sim_path}');run('{
                self.sim_file}');",
        ]
        self.out_srv.matlab_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def start(self, pm: PerformanceMonitor) -> None:
        """Start the TCP servers and MATLAB process.
        Args:
            pm (PerformanceMonitor): Performance monitor instance.
        """
        self.start_time = time.time()
        self.out_srv.start()
        self.in_srv.start()
        logger.debug("[INTERACTIVE] TCP servers started on %s:%s and %s:%s",
                     self.out_srv.host, self.out_srv.port,
                     self.in_srv.host, self.in_srv.port)
        self._start_matlab()
        logger.debug("[INTERACTIVE] Waiting for MATLAB to start...")
        pm.record_matlab_startup_complete()
        self.out_srv.accept()
        self.in_srv.accept()
        # Perform a handshake with MATLAB
        self.out_srv.send({})  # handshake

    # ------------------------------------------------------------------
    def _relay(self, payload: Dict[str, Any]) -> None:
        """Relay a response from the MATLAB process to the broker
        including the full simulation output."""

        msg = create_response(
            "interactive",
            self.sim_file,
            "interactive",
            self.templates,
            data=payload,
            sequence=self.sequence,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id,
        )
        msg["output"] = payload
        self.broker.send_result(self.source, msg)
        self.sequence += 1

    @staticmethod
    def _only_inputs(frame: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only the inputs from the frame."""
        if isinstance(frame, dict):
            sim = frame.get("simulation")
            if isinstance(sim, dict) and "inputs" in sim:
                logger.debug(
                    "[INTERACTIVE] Received inputs: %s",
                    sim["inputs"])
                return sim["inputs"]
        return frame

    def run(self, pm: PerformanceMonitor, msg_dict: Dict[str, Any]) -> None:
        """Run the interactive simulation loop."""
        sim = msg_dict["simulation"]
        stream_key = sim["inputs"]["stream_source"].replace("rabbitmq://", "")

        ch = self.broker.channel
        qname = f"Q.{self.agent_id}.interactive.{self.request_id}"
        ch.exchange_declare(
            "ex.input.stream",
            exchange_type="topic",
            durable=True)
        ch.queue_declare(queue=qname, durable=True)
        ch.queue_bind(
            exchange="ex.input.stream",
            queue=qname,
            routing_key=stream_key)

        try:
            while True:
                method, properties, body = ch.basic_get(
                    queue=qname, auto_ack=True)
                while method:
                    frame = _parse_frame(body)
                    if frame:
                        # Send the inputs to MATLAB
                        self.in_srv.send(self._only_inputs(frame))
                    method, properties, body = ch.basic_get(
                        queue=qname, auto_ack=True)

                # Receive Responses from MATLAB
                for resp in self.out_srv.recv_all():
                    # Send the response to the broker
                    self._relay(resp)
        finally:
            pm.record_simulation_complete()

    def close(self) -> None:
        """Close the TCP servers"""
        self.out_srv.close()
        self.in_srv.close()

    def metadata(self) -> Dict[str, Any]:
        meta: Dict[str, Any] = {}
        if self.start_time:
            meta["execution_time"] = time.time() - self.start_time
        meta["memory_usage"] = psutil.Process(
        ).memory_info().rss // (1024 * 1024)
        return meta


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
    logger.debug(
        "[INTERACTIVE] Starting interactive simulation: %s",
        sim["file"])
    controller = MatlabInteractiveController(
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
        controller.start(pm)
        controller.run(pm, msg_dict)
    except Exception as exc:  # pragma: no cover - runtime errors
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
        controller.close()
