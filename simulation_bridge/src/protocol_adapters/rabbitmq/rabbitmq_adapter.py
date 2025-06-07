"""RabbitMQ adapter for message transport between simulation components."""
import json
import threading
import functools
from typing import Dict, Any

import pika
import yaml
from blinker import signal

from ...utils.config_manager import ConfigManager
from ...utils.logger import get_logger
from ...utils.signal_manager import SignalManager
from ..base.protocol_adapter import ProtocolAdapter
from ...core.bridge_core import BridgeCore

logger = get_logger()


class RabbitMQAdapter(ProtocolAdapter):
    """
    Protocol adapter for RabbitMQ message broker.

    Handles connections to RabbitMQ, subscribes to configured queues,
    and processes incoming/outgoing messages.
    """

    def _get_config(self) -> Dict[str, Any]:
        """Retrieve RabbitMQ configuration from config manager."""
        return self.config_manager.get_rabbitmq_config()

    def __init__(self, config_manager: ConfigManager):
        """
        Initialize RabbitMQ adapter with configuration.

        Args:
            config_manager: Configuration manager providing RabbitMQ settings
        """
        super().__init__(config_manager)
        logger.debug("RabbitMQ adapter initialized")

        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.config['host'],
                port=self.config['port'],
                virtual_host=self.config['virtual_host']
            )
        )
        self.channel = self.connection.channel()
        self._consumer_thread = None
        self._running = False

        # Get all queues from config and register callback for each
        queues = self.config.get('infrastructure', {}).get('queues', [])
        for queue in queues:
            queue_name = queue.get('name')
            if queue_name:
                cb = functools.partial(
                    self._process_message, queue_name=queue_name)
                self.channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=cb,
                    auto_ack=False
                )
                logger.debug("Subscribed to queue: %s", queue_name)
        logger.debug("RabbitMQ adapter initialized and subscribed to queues")

    def _process_message(self, ch, method, properties, body, queue_name):
        """
        Process incoming RabbitMQ message.

        Args:
            ch: Channel object
            method: Method details
            properties: Message properties
            body: Message body
            queue_name: Source queue name
        """
        try:
            # Try to parse message as YAML first, then JSON, or fall back to
            # raw string
            try:
                message = yaml.safe_load(body)
            except Exception:
                try:
                    message = json.loads(body)
                except Exception:
                    message = {
                        "content": body.decode('utf-8', errors='replace'),
                        "raw_message": True
                    }

            if not isinstance(message, dict):
                raise ValueError("Message is not a dictionary")

            simulation = message.get('simulation', {})
            producer = simulation.get('client_id', 'unknown')
            consumer = simulation.get('simulator', 'unknown')

            signal_name = None
            kwargs = {
                "message": message,
                "producer": producer,
                "consumer": consumer,
            }

            if queue_name == 'Q.bridge.input':
                signal_name = 'message_received_input_rabbitmq'
                kwargs["protocol"] = 'rabbitmq'
            elif queue_name == 'Q.bridge.result':
                protocol = message.get(
                    'bridge_meta', '{}').get(
                    'protocol', 'unknown')
                if protocol == 'rest':
                    signal_name = 'message_received_result_rest'
                elif protocol == 'mqtt':
                    signal_name = 'message_received_result_mqtt'
                elif protocol == 'rabbitmq':
                    signal_name = 'message_received_result_rabbitmq'
            signal(signal_name).send(self, **kwargs)

            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.debug(
                "Message processed from queue %s: %s",
                queue_name, method.routing_key
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            logger.error(
                "Error processing message from %s: %s",
                queue_name,
                exc)

    def _run_consumer(self):
        """Run the RabbitMQ consumer in a separate thread."""
        logger.debug("RabbitMQ consumer thread started")
        try:
            self._running = True
            self.channel.start_consuming()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            if self._running:
                logger.error("RabbitMQ - Error in consumer thread: %s", exc)
        finally:
            logger.debug("RabbitMQ consumer thread exiting")
            self._running = False

    def start(self) -> None:
        """Start the RabbitMQ consumer in a separate thread."""
        logger.debug("RabbitMQ adapter starting...")
        try:
            self._consumer_thread = threading.Thread(
                target=self._run_consumer, daemon=True)
            self._consumer_thread.start()
            logger.debug("RabbitMQ consumer thread started successfully")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("RabbitMQ - Error starting consumer thread: %s", exc)
            self.stop()
            raise

    def stop(self) -> None:
        """Stop the RabbitMQ adapter and clean up resources."""
        logger.debug("RabbitMQ - Stopping adapter")
        self._running = False
        try:
            if self.channel and self.channel.is_open:
                def stop_consuming_from_thread():
                    try:
                        self.channel.stop_consuming()
                    except Exception as e:
                        logger.warning(
                            "RabbitMQ - Error stopping consuming: %s", e)
                self.connection.add_callback_threadsafe(
                    stop_consuming_from_thread)
        except Exception as e:
            logger.error(
                "RabbitMQ - Unexpected error while scheduling stop_consuming: %s", e)
        try:
            if self._consumer_thread and self._consumer_thread.is_alive():
                self._consumer_thread.join(timeout=5)
        except Exception as e:
            logger.warning("RabbitMQ - Error joining consumer thread: %s", e)
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
        except Exception as e:
            logger.warning("RabbitMQ - Error closing connection: %s", e)
        logger.debug("RabbitMQ - Adapter stopped cleanly")

    def _handle_message(self, message: Dict[str, Any]) -> None:
        """
        Handle incoming messages (required by ProtocolAdapter).

        Args:
            message: The message to process
        """
        self._process_message(None, None, None, message, 'Q.bridge.input')

    def _start_adapter(self) -> None:
        """Start the RabbitMQ consumer."""
        logger.debug("RabbitMQ adapter started...")
        try:
            self.channel.start_consuming()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("RabbitMQ - Error in consumer: %s", exc)
            raise
