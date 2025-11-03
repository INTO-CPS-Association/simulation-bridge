import json
import socket
import threading
from typing import Any, Callable, Dict, Optional

from ..comm.rabbitmq.rabbitmq_manager import RabbitMQManager
from ..utils.create_response import create_response
from ..utils.logger import get_logger
from ..utils.performance_monitor import PerformanceMonitor

logger = get_logger()


class Listener:
    def __init__(
        self,
        config: Dict[str, Any],
        destination: str,
        request_id: str,
        sim_file: str,
        bridge_meta: Optional[Any] = None,
        *,
        host: Optional[str] = None,
        output_port: Optional[int] = None,
        sim_type: str = 'streaming',
        on_complete: Optional[Callable[[str], None]] = None,
    ) -> None:
        udp_cfg = (config.get('udp', {}) or {})
        self.host = host if host is not None else udp_cfg.get(
            'host', 'localhost')
        self.output_port = output_port if output_port is not None else int(
            udp_cfg.get('output_port', 9876))
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._sequence = 0
        self.config = config
        self.destination = destination
        self.request_id = request_id
        self.sim_file = sim_file
        self.sim_type = sim_type
        self.bridge_meta = bridge_meta or 'unknown'
        self.response_templates = self.config.get('response_templates', {})
        agent_cfg = (self.config.get('agent', {}) or {})
        agent_id = agent_cfg.get('agent_id', 'anylogic')
        self.message_broker = RabbitMQManager(agent_id, self.config)
        self._on_complete = on_complete

    def start(self) -> None:
        """Start UDP listening loop for the configured simulation."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            with self._lock:
                self._sock = sock
            try:
                sock.bind((self.host, self.output_port))
            except OSError as exc:
                logger.error(
                    "UDP listener failed to bind %s:%s for %s: %s",
                    self.host,
                    self.output_port,
                    self.sim_file,
                    exc,
                )
                self._ready_event.set()
                return
            logger.info(
                "UDP listening on %s:%s for %s (request %s)",
                self.host,
                self.output_port,
                self.sim_file,
                self.request_id,
            )
            self._ready_event.set()
            try:
                while not self._stop_event.is_set():
                    try:
                        data, addr = sock.recvfrom(4096)
                    except OSError as e:
                        # Socket closed during shutdown or other error
                        if self._stop_event.is_set():
                            break
                        logger.error(f"Socket error while receiving: {e}")
                        break

                    msg_text = data.decode("utf-8")
                    logger.debug("Received from %s: %s", addr, msg_text)
                    try:
                        msg = json.loads(msg_text)
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON")
                        continue
                    self._process_output(msg)
            except KeyboardInterrupt:
                logger.info("\nStopped by user.")
            finally:
                # Clear reference for safety
                with self._lock:
                    self._sock = None
                self._ready_event.clear()

    def wait_until_ready(self, timeout: float = 5.0) -> bool:
        """Wait until the socket bind succeeds or fails."""
        return self._ready_event.wait(timeout)

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _process_output(self, output: Dict[str, Any]) -> None:
        """Process and send individual output chunk."""
        if self._is_completion_message(output):
            self._handle_completion(output)
            return

        template_type = 'progress' if 'progress' in output else 'streaming'
        data_payload = output
        progress = (output.get('progress') or {}).get(
            'percentage') if template_type == 'progress' else None
        message = (output.get('progress') or {}).get(
            'message') if template_type == 'progress' else None
        metadata = output.get('metadata') or output.get('simulation_info') or {}

        response = create_response(
            template_type,
            self.sim_file,
            self.sim_type,
            self.response_templates,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id,
            data=data_payload,
            metadata=metadata,
            sequence=self._next_sequence(),
            percentage=progress,
            message=message,
        )

        if not self._ensure_broker_connected():
            return

        try:
            success = self.message_broker.send_result(
                destination=self.destination, result=response)
        except Exception as exc:
            logger.error(
                "Error sending streaming result for %s (request %s): %s",
                self.sim_file,
                self.request_id,
                exc,
            )
            return

        if success:
            PerformanceMonitor().record_result_sent()
        else:
            logger.error(
                "Failed to send streaming result for %s (request %s)",
                self.sim_file,
                self.request_id,
            )

    def _ensure_broker_connected(self) -> bool:
        if getattr(self.message_broker, 'channel',
                   None) and self.message_broker.channel.is_open:
            return True
        if not self.message_broker.connect():
            logger.error(
                "Unable to connect to RabbitMQ for streaming results (%s, request %s)",
                self.sim_file,
                self.request_id,
            )
            return False
        return True

    def _is_completion_message(self, output: Dict[str, Any]) -> bool:
        status = output.get('status')
        if isinstance(status, str) and status.lower() == 'completed':
            return True
        data_status = (output.get('data') or {}).get(
            'status') if isinstance(output.get('data'), dict) else None
        if isinstance(data_status, str) and data_status.lower() == 'completed':
            return True
        return False

    def _handle_completion(self, output: Dict[str, Any]) -> None:
        perf_monitor = PerformanceMonitor()

        data_payload = output.get('data', {}) if isinstance(
            output.get('data'), dict) else {}
        metadata = output.get('metadata') or output.get('simulation_info') or {}

        success = False
        perf_monitor.record_simulation_complete()
        if self._ensure_broker_connected():
            try:
                response = create_response(
                    template_type='success',
                    sim_file=self.sim_file,
                    sim_type=self.sim_type,
                    response_templates=self.response_templates,
                    bridge_meta=self.bridge_meta,
                    request_id=self.request_id,
                    data=data_payload,
                    metadata=metadata,
                )
                success = self.message_broker.send_result(
                    destination=self.destination, result=response)
            except Exception as exc:
                logger.error(
                    "Error sending completion result for %s (request %s): %s",
                    self.sim_file,
                    self.request_id,
                    exc,
                )
                success = False
        else:
            logger.error(
                "Completion detected for %s (request %s) but RabbitMQ connection is unavailable",
                self.sim_file,
                self.request_id,
            )

        if success:
            perf_monitor.record_result_sent()
            logger.info(
                "Sent completion result for %s (request %s)",
                self.sim_file,
                self.request_id,
            )
        else:
            logger.error(
                "Failed to send completion result for %s (request %s)",
                self.sim_file,
                self.request_id,
            )

        perf_monitor.record_matlab_stop()
        perf_monitor.complete_operation()

        if self._on_complete:
            try:
                self._on_complete(self.request_id)
            except Exception:
                logger.exception(
                    "Error while executing completion callback for request %s",
                    self.request_id,
                )

        self.stop()

    def stop(self) -> None:
        """Signal the listener loop to stop."""
        self._stop_event.set()
        # Close the socket to immediately unblock recvfrom()
        with self._lock:
            if self._sock is not None:
                try:
                    self._sock.close()
                except OSError:
                    pass
        self._ready_event.clear()
        try:
            self.message_broker.close()
        except Exception:
            pass
