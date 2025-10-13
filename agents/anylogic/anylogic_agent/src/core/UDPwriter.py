import json
import socket
import threading
from typing import Any, Callable, Dict, Optional

import pika
import yaml

from ..comm.rabbitmq.rabbitmq_manager import RabbitMQManager
from ..utils.create_response import create_response
from ..utils.logger import get_logger

logger = get_logger()


class Writer:
    def __init__(
        self,
        config: Dict[str, Any],
        destination: str,
        request_id: str,
        sim_file: str,
        stream_key: str,
        bridge_meta: Optional[Any] = None,
        *,
        host: Optional[str] = None,
        input_port: Optional[int] = None,
        sim_type: str = 'interactive',
        on_complete: Optional[Callable[[str], None]] = None,
    ) -> None:
        udp_cfg = (config.get('udp', {}) or {})
        self.host = host if host is not None else udp_cfg.get(
            'host', 'localhost')
        self.input_port = input_port if input_port is not None else int(
            udp_cfg.get('input_port', 9877))
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._sequence = 0
        self.config = config
        self.destination = destination
        self.request_id = request_id
        self.stream_key = stream_key
        self.sim_file = sim_file
        self.sim_type = sim_type
        self.bridge_meta = bridge_meta or 'unknown'
        self.response_templates = self.config.get('response_templates', {})
        agent_cfg = (self.config.get('agent', {}) or {})
        agent_id = agent_cfg.get('agent_id', 'anylogic')
        self.message_broker = RabbitMQManager(agent_id, self.config)
        self._on_complete = on_complete

    def start(self) -> None:
        """Listen for incoming RabbitMQ messages and forward them via UDP."""
        # Setup RabbitMQ connection
        rabbitmq_cfg = self.config.get('rabbitmq', {})
        credentials = pika.PlainCredentials(
            rabbitmq_cfg.get('username', 'guest'),
            rabbitmq_cfg.get('password', 'guest'),
        )
        connection_params = pika.ConnectionParameters(
            host=rabbitmq_cfg.get('host', 'localhost'),
            port=rabbitmq_cfg.get('port', 5672),
            virtual_host=rabbitmq_cfg.get('vhost', '/'),
            credentials=credentials,
            heartbeat=rabbitmq_cfg.get('heartbeat', 600),
        )
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()

        # Subscribe to the command queue
        command_queue = f"Q.{self.destination}.interactive.{self.request_id}"
        channel.queue_declare(queue=command_queue, durable=True)
        channel.queue_bind(
            exchange="ex.input.stream",
            queue=command_queue,
            routing_key=self.stream_key,
        )

        """Start UDP writer loop for the configured simulation."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            with self._lock:
                self._sock = sock
            logger.info(
                "UDP writer forwarding to %s:%s for %s (request %s)",
                self.host,
                self.input_port,
                self.sim_file,
                self.request_id,
            )
            self._ready_event.set()

            def callback(ch, method, properties, body):
                msg = yaml.safe_load(body)
                self._send_udp(sock, msg)
                ch.basic_ack(method.delivery_tag)
                logger.debug(
                    "Forwarded message to %s:%s for %s (request %s): %s",
                    self.host,
                    self.input_port,
                    self.sim_file,
                    self.request_id,
                    msg,
                )

            channel.basic_consume(
                queue=command_queue,
                on_message_callback=callback)
            try:
                channel.start_consuming()
            except (KeyboardInterrupt, EOFError):
                logger.info("Stopped by user.")
                channel.stop_consuming()
                connection.close()
                self.stop()

    def wait_until_ready(self, timeout: float = 5.0) -> bool:
        """Wait until the socket is ready to send."""
        return self._ready_event.wait(timeout)

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _send_udp(self, sock: socket.socket, msg: dict) -> None:
        data = json.dumps(msg).encode("utf-8")
        try:
            sock.sendto(data, (self.host, self.input_port))
            logger.debug("Sent to %s:%s: %s", self.host, self.input_port, data)
        except Exception as exc:
            logger.error("Error sending UDP message: %s", exc)

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

    def stop(self) -> None:
        """Signal the writer loop to stop."""
        self._stop_event.set()
        # Close the socket to immediately unblock sendto()
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
