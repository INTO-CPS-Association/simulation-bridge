"""
Core bridge module for message routing between different protocols.

This module handles message routing between RabbitMQ, MQTT, and REST protocols,
providing a unified interface for cross-protocol communication.
"""

from typing import Dict, Any
import json
import ssl
import pika
from pydantic import BaseModel
from ..utils.config_manager import ConfigManager
from ..utils.logger import get_logger
from ..utils.performance_monitor import PerformanceMonitor

# Constants for RabbitMQ connection parameters
RABBITMQ_HEARTBEAT = 600  # 10 minutes heartbeat
RABBITMQ_BLOCKED_CONNECTION_TIMEOUT = 300  # 5 minutes timeout
RABBITMQ_CONNECTION_ATTEMPTS = 3  # Number of connection attempts
RABBITMQ_RETRY_DELAY = 5  # Delay between retries in seconds


logger = get_logger()

# Pydantic models for message validation


class SimulationModel(BaseModel):
    "Represents the details of a simulation request."
    request_id: str
    client_id: str
    simulator: str
    type: str
    file: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]


class MessageModel(BaseModel):
    "Represents a message structure for simulation requests."
    simulation: SimulationModel


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

            try:
                credentials = pika.PlainCredentials(
                    self.config['username'],
                    self.config['password']
                )

                if self.config.get('tls', False):
                    context = ssl.create_default_context()
                    ssl_options = pika.SSLOptions(context, self.config['host'])
                    connection_params = pika.ConnectionParameters(
                        host=self.config['host'],
                        port=self.config['port'],
                        virtual_host=self.config['vhost'],
                        credentials=credentials,
                        ssl_options=ssl_options
                    )
                else:
                    connection_params = pika.ConnectionParameters(
                        host=self.config['host'],
                        port=self.config['port'],
                        virtual_host=self.config['vhost'],
                        credentials=credentials
                    )

                self.connection = pika.BlockingConnection(connection_params)

            except (pika.exceptions.AMQPConnectionError, ssl.SSLError) as e:
                logger.error(
                    "Failed to connect to RabbitMQ at %s:%s with TLS=%s",
                    self.config['host'], self.config['port'], self.config.get(
                        'tls', False)
                )
                logger.error("Error: %s", e)
                raise RuntimeError(
                    "Connection failed. Check TLS settings and port.") from e

            except Exception as e:
                logger.error(
                    "Unexpected error while connecting to RabbitMQ: %s", e)
                raise
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
        # Initialize performance monitor
        performance_monitor = PerformanceMonitor()
        message_dict = kwargs.get('message', {})
        operation_id = message_dict.get(
            'simulation', {}).get(
            'request_id', 'unknown')
        performance_monitor.record_core_received_input(operation_id)
        try:
            message = MessageModel.model_validate(message_dict)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Invalid message format: %s", e)
            return
        simulation = message.simulation
        if simulation is None:
            request_id = 'unknown'
        else:
            request_id = simulation.request_id if simulation.request_id else 'unknown'
        producer = kwargs.get('producer', 'unknown')
        consumer = kwargs.get('consumer', 'unknown')
        protocol = kwargs.get('protocol', 'unknown')
        logger.info(
            "[%s] Handling incoming simulation request with ID: %s", protocol.upper(), request_id)
        self._publish_message(
            producer,
            consumer,
            message.model_dump(),
            protocol=protocol, operation_id=operation_id)

    def handle_result_rabbitmq_message(self, sender, **kwargs):  # pylint: disable=unused-argument
        """
        Handle RabbitMQ result messages.

        Args:
            **kwargs: Keyword arguments containing message data
        """
        # Initialize performance monitor
        performance_monitor = PerformanceMonitor()
        message = kwargs.get('message', {})
        producer = message.get('source', 'unknown')
        consumer = "result"
        operation_id = message.get('request_id', 'unknown')
        self._publish_message(
            producer,
            consumer,
            message,
            exchange='ex.bridge.result',
            protocol='rabbitmq',
            operation_id=operation_id)
        status = message.get('status', 'unknown')
        performance_monitor.record_result_sent(operation_id)
        if status == 'completed':
            performance_monitor.finalize_operation(operation_id)

    def handle_result_unknown_message(self, sender, **kwargs):  # pylint: disable=unused-argument
        """
        Handle RabbitMQ result messages.

        Args:
            **kwargs: Keyword arguments containing message data
        """
        message = kwargs.get('message', {})
        logger.error(
            "Received error result message with unknown protocol: %s", message['error'])

    def _publish_message(self, producer, consumer, message,  # pylint: disable=too-many-arguments, too-many-positional-arguments
                         exchange='ex.bridge.output', protocol='unknown', operation_id='unknown'):
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

        # Initialize performance monitor
        performance_monitor = PerformanceMonitor()

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
            # Record sent input time in performance monitor
            if exchange == 'ex.bridge.output':
                performance_monitor.record_core_sent_input(operation_id)
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
