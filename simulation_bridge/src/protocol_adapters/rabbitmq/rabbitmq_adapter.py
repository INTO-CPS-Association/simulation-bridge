import json
import ssl
import threading
import functools
from typing import Dict, Any, Tuple

import pika
import yaml
from blinker import signal

from ...utils.config_manager import ConfigManager
from ...utils.performance_monitor import PerformanceMonitor
from ...utils.logger import get_logger
from ..base.protocol_adapter import ProtocolAdapter

logger = get_logger()


class RabbitMQAdapter(ProtocolAdapter):
    """
    Protocol adapter for RabbitMQ message broker.

    Handles connections to RabbitMQ, subscribes to configured queues,
    and processes incoming/outgoing messages.
    """

    def _get_config(self) -> Dict[str, Any]:
        return self.config_manager.get_rabbitmq_config()

    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        credentials = pika.PlainCredentials(
            self.config["username"],
            self.config["password"]
        )
        if self.config.get("tls", False):
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_options = pika.SSLOptions(context, self.config["host"])
            params = pika.ConnectionParameters(
                host=self.config["host"],
                port=self.config["port"],
                virtual_host=self.config["vhost"],
                credentials=credentials,
                ssl_options=ssl_options
            )
        else:
            params = pika.ConnectionParameters(
                host=self.config["host"],
                port=self.config["port"],
                virtual_host=self.config["vhost"],
                credentials=credentials
            )
        self.connection = pika.BlockingConnection(params)
        self.channel = self.connection.channel()
        self._consumer_thread = None
        self._running = False
        queues = self.config.get("infrastructure", {}).get("queues", [])
        for queue in queues:
            qname = queue.get("name")
            if qname:
                cb = functools.partial(self._process_message, queue_name=qname)
                self.channel.basic_consume(
                    queue=qname,
                    on_message_callback=cb,
                    auto_ack=False
                )

    @staticmethod
    def _parse_body(body: bytes) -> Dict[str, Any]:
        for loader in (yaml.safe_load, json.loads):
            try:
                msg = loader(body)
                if isinstance(msg, dict):
                    return msg
            except Exception:
                continue
        return {
            "content": body.decode("utf-8", errors="replace"),
            "raw_message": True
        }

    @staticmethod
    def _clean_bridge_meta(data: Any) -> Dict[str, Any]:
        if isinstance(data, str) and data.strip().startswith("{"):
            try:
                data = json.loads(data)
            except Exception:
                logger.warning("Malformed JSON in bridge_meta: %s", data)
                data = {}
        return data if isinstance(data, dict) else {}

    def _handle_input_queue(
        self, message: Dict[str, Any], pm: PerformanceMonitor
    ) -> Tuple[str, Dict[str, Any]]:
        sim = message.get("simulation", {})
        producer = sim.get("client_id", "unknown")
        consumer = sim.get("simulator", "unknown")
        op_id = sim.get("request_id", "unknown")
        sim_type = sim.get("type", "unknown")
        pm.start_operation(op_id, client_id=producer,
                           protocol="rabbitmq", simulation_type=sim_type)
        kwargs = {
            "message": message,
            "producer": producer,
            "consumer": consumer,
            "protocol": "rabbitmq"
        }
        return "message_received_input_rabbitmq", kwargs

    def _handle_result_queue(
        self, message: Dict[str, Any], pm: PerformanceMonitor
    ) -> Tuple[str, Dict[str, Any]]:
        op_id = message.get("request_id", "unknown")
        dest = message.get("destinations", [])
        producer = dest[0] if dest else "unknown"
        consumer = message.get("source", "unknown")
        sim_type = message.get("simulation", {}).get("type", "unknown")
        meta = self._clean_bridge_meta(message.get("bridge_meta", {}))
        protocol = meta.get("protocol", "unknown")
        pm.record_core_received_result(op_id, protocol, producer, sim_type)
        kwargs = {
            "message": message,
            "producer": producer,
            "consumer": consumer,
            "protocol": "rabbitmq"
        }
        signals = {
            "rest": "message_received_result_rest",
            "mqtt": "message_received_result_mqtt",
            "rabbitmq": "message_received_result_rabbitmq",
            "inmemory": "message_received_result_inmemory"
        }
        return signals.get(protocol, "message_received_result_unknown"), kwargs

    def _process_message(self, ch, method, properties, body, queue_name):
        try:
            message = self._parse_body(body)
            if not isinstance(message, dict):
                raise ValueError("Message is not a dictionary")
            pm = PerformanceMonitor()
            if queue_name == "Q.bridge.input":
                sig, kwargs = self._handle_input_queue(message, pm)
            elif queue_name == "Q.bridge.result":
                sig, kwargs = self._handle_result_queue(message, pm)
            else:
                raise ValueError(f"Unhandled queue {queue_name}")
            signal(sig).send(self, **kwargs)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.debug("Message processed from queue %s", queue_name)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            logger.error(
                "Error processing message from %s: %s",
                queue_name,
                exc)

    def _run_consumer(self):
        logger.debug("RabbitMQ consumer thread started")
        try:
            self._running = True
            self.channel.start_consuming()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            if self._running:
                logger.error("RabbitMQ - Error in consumer thread: %s", exc)
        finally:
            self._running = False

    def start(self) -> None:
        logger.debug("RabbitMQ adapter starting...")
        self._consumer_thread = threading.Thread(
            target=self._run_consumer, daemon=True)
        self._consumer_thread.start()

    def stop(self) -> None:
        self._running = False
        if threading.current_thread() is self._consumer_thread:
            return
        if self.channel and self.channel.is_open:
            def stop_c():
                try:
                    self.channel.stop_consuming()
                except Exception as e:
                    logger.warning("RabbitMQ - Error stopping consuming: %s", e)
            self.connection.add_callback_threadsafe(stop_c)
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5)
        if self.connection and self.connection.is_open:
            self.connection.close()

    def _handle_message(self, message: Dict[str, Any]) -> None:
        self._process_message(None, None, None, message, "Q.bridge.input")

    def _start_adapter(self) -> None:
        logger.debug("RabbitMQ adapter started...")
        try:
            self.channel.start_consuming()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("RabbitMQ - Error in consumer: %s", exc)
            raise
