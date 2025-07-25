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
from ..utils.constants import (
    ACCEPT_TIMEOUT,
    BUFFER_SIZE,
    BYTES_IN_MB,
    DEFAULT_INPUT_PORT,
    DEFAULT_OUTPUT_PORT,
    MAX_FILENAME_LENGTH,
    EXCHANGE_INPUT_STREAM
)

logger = get_logger()


def _parse_frame(body: bytes) -> Dict[str, Any]:
    """Decode a YAML frame received from RabbitMQ."""
    try:
        return yaml.safe_load(body)
    except yaml.YAMLError as exc:  # pragma: no cover - logging only
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
        ready = select([self._srv], [], [], ACCEPT_TIMEOUT)
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
        # Read up to BUFFER_SIZE bytes from socket and append to internal buffer
        # (self._buffer)
        self._buffer += self._conn.recv(BUFFER_SIZE)
        # Messages are sent with a "\n" character as delimiter.
        # Split everything received into "lines".
        lines = self._buffer.split(b"\n")
        self._buffer = lines[-1]
        messages: list[Dict[str, Any]] = []
        # For each complete line:
        # Remove leading/trailing whitespace and CR.
        # If the line is empty, skip it.
        # Try to decode it from JSON.
        # Success → add the dict to the messages list.
        # Failure → log the error and still add an object
        # {"error": "Invalid JSON: …"} so downstream code can handle
        # the exception without crashing the server.
        for line in lines[:-1]:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line.decode()))
            except json.JSONDecodeError as exc:  # pragma: no cover - logs error and skips invalid message
                logger.error("[INTERACTIVE] Invalid JSON: %s", exc)
                messages.append({"error": f"Invalid JSON: {str(exc)}"})
        # Return the messages list, i.e., all complete decoded JSON objects (plus any error placeholders) available at that moment.
        # The next call to recv_all() will resume from where it left off,
        # because only the last incomplete fragment remains in the buffer.
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
        if len(file) > MAX_FILENAME_LENGTH:
            raise ValueError("Simulation file name too long")
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
            tcp_cfg.get("output_port", DEFAULT_OUTPUT_PORT),
        )
        self.in_srv = _TcpServer(
            tcp_cfg.get("host", "localhost"),
            tcp_cfg.get("input_port", DEFAULT_INPUT_PORT),
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
        """Relay a response from the MATLAB process to the broker,
        including the full simulation output."""

        status = payload.get("status", "unknown")
        is_completed = status == "completed"
        message_type = "completed" if is_completed else "working"

        msg = create_response(
            message_type,
            self.sim_file,
            "interactive",
            self.templates,
            data=payload,
            sequence=self.sequence,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id,
        )

        # Attach raw output only if not completed
        if not is_completed:
            msg["output"] = payload
        else:
            logger.info("[INTERACTIVE] Simulation completed successfully.")

        self.broker.send_result(self.source, msg)
        self.sequence += 1

    @staticmethod
    def _only_inputs(frame: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only the inputs section from a simulation frame"""
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
            exchange=EXCHANGE_INPUT_STREAM,
            exchange_type="topic",
            durable=True)
        ch.queue_declare(queue=qname, durable=True)
        ch.queue_bind(
            exchange=EXCHANGE_INPUT_STREAM,
            queue=qname,
            routing_key=stream_key)

        try:
            while True:
                if self.out_srv.matlab_proc and self.out_srv.matlab_proc.poll() is not None:
                    logger.debug(
                        "[INTERACTIVE] MATLAB process ended, stopping loop")
                    break
                method, _, body = ch.basic_get(
                    queue=qname, auto_ack=True)
                while method:
                    frame = _parse_frame(body)
                    if frame:
                        # Send the inputs to MATLAB
                        self.in_srv.send(self._only_inputs(frame))
                    method, _, body = ch.basic_get(
                        queue=qname, auto_ack=True)

                # Receive Responses from MATLAB
                for resp in self.out_srv.recv_all():
                    # If the response contains a status, check if it's completed
                    if resp.get("status") == "completed":
                        self._relay(resp)
                        logger.debug("[INTERACTIVE] Received completion signal")
                        return
                    # Send the response to the broker
                    self._relay(resp)
        except KeyboardInterrupt:  # pragma: no cover - manual interruption
            logger.info("[INTERACTIVE] Interrupted by user")
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
        ).memory_info().rss // BYTES_IN_MB
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
    except (KeyError, ValueError) as exc:  # Handle specific known errors
        logger.error("[INTERACTIVE] Known error: %s", exc)
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
    except Exception as exc:  # pragma: no cover - unexpected errors
        logger.exception("[INTERACTIVE] Unexpected error: %s", exc)
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
