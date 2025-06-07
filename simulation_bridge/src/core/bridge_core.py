"""
Core bridge module for message routing between different protocols.

This module handles message routing between RabbitMQ, MQTT, and REST protocols,
providing a unified interface for cross-protocol communication.
"""

import json
import pika
from ..utils.config_manager import ConfigManager
from ..utils.logger import get_logger
from ..utils.signal_manager import SignalManager

logger = get_logger()


class BridgeCore:
    """
    Core bridge class for handling message routing between different protocols.

    Manages connections to RabbitMQ, MQTT, and REST endpoints, and routes
    messages between them based on protocol metadata.
    """

    def __init__(self, config_manager: ConfigManager, adapters: dict):
        """
        Initialize the bridge core with configuration and adapters.

        Args:
            config_manager: Configuration manager instance
            adapters: Dictionary of protocol adapters
        """
        self.config = config_manager.get_rabbitmq_config()
        self.connection = None
        self.channel = None
        self._initialize_rabbitmq_connection()
        self.adapters = adapters
        logger.debug("Signals connected and bridge core initialized")

    def _initialize_rabbitmq_connection(self):
        """Initialize or reinitialize the RabbitMQ connection."""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()

            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.config['host'],
                    port=self.config['port'],
                    virtual_host=self.config['virtual_host'],
                    heartbeat=600,  # 10 minutes heartbeat
                    blocked_connection_timeout=300,  # 5 minutes timeout
                    connection_attempts=3,  # Number of connection attempts
                    retry_delay=5  # Delay between retries in seconds
                )
            )
            self.channel = self.connection.channel()
            logger.debug("RabbitMQ connection established successfully")
        except pika.exceptions.AMQPConnectionError as e:
            logger.error("Failed to initialize RabbitMQ connection: %s", e)
            raise
        except pika.exceptions.AMQPChannelError as e:
            logger.error("Failed to initialize RabbitMQ channel: %s", e)
            raise

    def _ensure_connection(self):
        """Ensure the RabbitMQ connection is active, reconnect if necessary."""
        try:
            if not self.connection or self.connection.is_closed:
                logger.warning(
                    "RabbitMQ connection is closed, attempting to reconnect...")
                self._initialize_rabbitmq_connection()
            return True
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError) as e:
            logger.error("Failed to ensure RabbitMQ connection: %s", e)
            return False

    def handle_input_message(self, sender, **kwargs):  # pylint: disable=unused-argument
        """
        Handle incoming messages.

        Args:
            **kwargs: Keyword arguments containing message data
        """
        message = kwargs.get('message', {})
        request_id = message.get(
            'simulation',
            'unknown').get(
            'request_id',
            'unknown')
        producer = kwargs.get('producer', 'unknown')
        consumer = kwargs.get('consumer', 'unknown')
        protocol = kwargs.get('protocol', 'unknown')
        logger.info(
            "[%s] Handling incoming simulation request with ID: %s", protocol.upper(), request_id)
        self._publish_message(producer, consumer, message, protocol=protocol)

    def handle_result_rabbitmq_message(self, sender, **kwargs):  # pylint: disable=unused-argument
        """
        Handle RabbitMQ result messages.

        Args:
            **kwargs: Keyword arguments containing message data
        """
        message = kwargs.get('message', {})
        producer = message.get('source', 'unknown')
        consumer = "result"
        self._publish_message(
            producer,
            consumer,
            message,
            exchange='ex.bridge.result',
            protocol='rabbitmq')

    def _publish_message(self, producer, consumer, message,
                         exchange='ex.bridge.output', protocol='unknown'):
        """
        Publish message to RabbitMQ exchange.

        Args:
            producer: Message producer identifier
            consumer: Message consumer identifier
            message: Message payload
            exchange: RabbitMQ exchange name
            protocol: Protocol identifier
        """
        if not self._ensure_connection():
            logger.error(
                "Cannot publish message: RabbitMQ connection is not available")
            return

        routing_key = f"{producer}.{consumer}"
        message['simulation']['bridge_meta'] = {
            'protocol': protocol
        }
        try:
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                )
            )
            logger.debug(
                "Message routed to exchange '%s': %s -> %s, protocol=%s",
                exchange, producer, consumer, protocol)
        except (pika.exceptions.AMQPConnectionError,
                pika.exceptions.AMQPChannelError) as e:
            logger.error("RabbitMQ connection error: %s", e)
            self._initialize_rabbitmq_connection()
            # Retry the publish operation once
            try:
                self.channel.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                    )
                )
                logger.debug(
                    "Message routed to exchange '%s' after reconnection: %s -> %s",
                    exchange, producer, consumer)
            except (pika.exceptions.AMQPConnectionError,
                    pika.exceptions.AMQPChannelError) as retry_e:
                logger.error(
                    "Failed to publish message after reconnection: %s", retry_e)

    def stop(self):
        """Stop the bridge core and clean up resources."""
        try:
            SignalManager.disconnect_all_signals()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.debug("Bridge core stopped")
        except (pika.exceptions.AMQPConnectionError,
                pika.exceptions.AMQPChannelError) as e:
            logger.error("Error stopping bridge core: %s", e)
