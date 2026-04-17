"""RabbitMQ connection manager and message publisher.

Provides a retry-capable publish method used by BridgeCore to send
messages to RabbitMQ exchanges.
"""

import json
import ssl
from typing import Any, Dict

import pika

from ..utils.logger import get_logger
from ..utils.performance_monitor import PerformanceMonitor
from .models import datetime_serializer

logger = get_logger()


class BridgePublisher:
    """Manages a persistent RabbitMQ connection and publishes messages."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.connection = None
        self.channel = None
        self._initialize_connection()

    def _build_connection_params(self):
        """Build pika ConnectionParameters from config."""
        credentials = pika.PlainCredentials(
            self.config['username'], self.config['password'])
        if self.config.get('tls', False):
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_options = pika.SSLOptions(
                context, self.config['host'])
            return pika.ConnectionParameters(
                host=self.config['host'],
                port=self.config['port'],
                virtual_host=self.config['vhost'],
                credentials=credentials,
                ssl_options=ssl_options,
            )
        return pika.ConnectionParameters(
            host=self.config['host'],
            port=self.config['port'],
            virtual_host=self.config['vhost'],
            credentials=credentials,
        )

    def _initialize_connection(self):
        """Open a RabbitMQ connection and channel."""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            self.connection = pika.BlockingConnection(
                self._build_connection_params())
            self.channel = self.connection.channel()
            logger.debug(
                "RabbitMQ connection established successfully")
        except (pika.exceptions.AMQPConnectionError,
                ssl.SSLError) as exc:
            logger.error("Failed to connect to RabbitMQ: %s", exc)
            raise
        except pika.exceptions.AMQPChannelError as exc:
            logger.error(
                "Failed to initialize RabbitMQ channel: %s", exc)
            raise

    def ensure_connection(self) -> bool:
        """Reconnect if needed. Returns True on success."""
        try:
            if not self.connection or self.connection.is_closed:
                logger.warning(
                    "RabbitMQ connection is closed, "
                    "attempting to reconnect...")
                self._initialize_connection()
            return True
        except (pika.exceptions.AMQPConnectionError,
                pika.exceptions.AMQPChannelError) as exc:
            logger.error(
                "Failed to ensure RabbitMQ connection: %s", exc)
            return False

    def publish(  # pylint: disable=too-many-arguments,too-many-positional-arguments
            self, producer, consumer, message,
            exchange='ex.bridge.output', protocol='unknown',
            operation_id='unknown'):
        """Publish a message with one retry on connection failure."""
        if not self.ensure_connection():
            logger.error(
                "Cannot publish message: "
                "RabbitMQ connection is not available")
            return
        routing_key = f"{producer}.{consumer}"
        sim = message.get('simulation')
        if isinstance(sim, dict):
            sim['bridge_meta'] = {'protocol': protocol}
        body = json.dumps(message, default=datetime_serializer)
        try:
            self._do_publish(exchange, routing_key, body)
            self._record_metrics(
                exchange, routing_key, protocol,
                producer, consumer, operation_id, message)
        except (pika.exceptions.AMQPConnectionError,
                pika.exceptions.AMQPChannelError) as exc:
            logger.error("RabbitMQ connection error: %s", exc)
            self._retry_publish(
                exchange, routing_key, body,
                producer, consumer)

    def _do_publish(self, exchange, routing_key, body):
        """Execute a single basic_publish call."""
        self.channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(delivery_mode=2),
        )

    def _retry_publish(self, exchange, routing_key, body,
                       producer, consumer):
        """Reconnect and retry publish once."""
        self._initialize_connection()
        try:
            self._do_publish(exchange, routing_key, body)
            logger.debug(
                "Message routed to exchange '%s' after "
                "reconnection: %s -> %s",
                exchange, producer, consumer)
        except (pika.exceptions.AMQPConnectionError,
                pika.exceptions.AMQPChannelError) as exc:
            logger.error(
                "Failed to publish message after "
                "reconnection: %s", exc)

    def _record_metrics(self, exchange, routing_key,
                        protocol, producer, consumer,
                        operation_id, message):
        """Log and record performance metrics for sent messages."""
        sim_type = message.get(
            'simulation', {}).get('type', 'unknown')
        logger.debug(
            "Message routed to exchange '%s': "
            "%s -> %s, protocol=%s",
            exchange, producer, consumer, protocol)
        if exchange == 'ex.bridge.output':
            pm = PerformanceMonitor()
            pm.record_core_sent_input(
                operation_id, protocol, producer, sim_type)
