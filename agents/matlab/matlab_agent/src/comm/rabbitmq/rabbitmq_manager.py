"""
RabbitMQManager class for managing RabbitMQ connections, exchanges, queues, and message handling.
This module provides functionality to establish connections with RabbitMQ,
set up exchanges and queues, and send/receive messages within a simulation agent framework.
"""
import sys
import uuid
from typing import Dict, Any, Callable, Optional

import yaml
import pika
import time
from pika.spec import BasicProperties

from .interfaces import IRabbitMQManager
from ...utils.logger import get_logger

logger = get_logger()


class RabbitMQManager(IRabbitMQManager):
    """
    Manager for RabbitMQ connections, channels, exchanges, and queues.
    Implements the IRabbitMQManager interface.
    """

    def __init__(self, agent_id: str, config: Dict[str, Any]) -> None:
        """
        Initialize the RabbitMQ manager.

        Args:
            agent_id (str): The ID of the agent
            config (dict): Configuration parameters
        """
        self.agent_id: str = agent_id
        self.config: Dict[str, Any] = config
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        self.input_queue_name: str = f'Q.sim.{self.agent_id}'
        self.message_handler: Optional[Callable[[
            pika.adapters.blocking_connection.BlockingChannel,
            pika.spec.Basic.Deliver, BasicProperties, bytes], None]] = None

    def connect(self) -> bool:
        """
        Establish connection to RabbitMQ server using configuration parameters.

        Returns:
            bool: True if connection and channel are open, False otherwise.
        """
        rabbitmq_config: Dict[str, Any] = self.config.get('rabbitmq', {})
        max_retries = 5
        retry_delay = 2

        for attempt in range(1, max_retries + 1):
            try:
                logger.debug("Connecting to RabbitMQ (attempt %d)...", attempt)
                credentials = pika.PlainCredentials(
                    rabbitmq_config.get('username', 'guest'),
                    rabbitmq_config.get('password', 'guest')
                )
                vhost = rabbitmq_config.get('vhost', '/')
                parameters = pika.ConnectionParameters(
                    host=rabbitmq_config.get('host', 'localhost'),
                    port=rabbitmq_config.get('port', 5672),
                    virtual_host=vhost,
                    credentials=credentials,
                    heartbeat=rabbitmq_config.get('heartbeat', 600)
                )
                self.connection = pika.BlockingConnection(parameters)

                if self.connection.is_open:
                    logger.debug(
                        "Connection to RabbitMQ is open. Attempting to create channel...")
                    self.channel = self.connection.channel()

                    if self.channel and self.channel.is_open:
                        logger.debug(
                            "Successfully connected to RabbitMQ and channel is open.")
                        return True
                    else:
                        logger.error("Channel creation failed. Retrying...")
                else:
                    logger.error(
                        "Connection opened but channel could not be created. Retrying...")

            except pika.exceptions.AMQPConnectionError as e:
                logger.error("Connection failed (attempt %d): %s", attempt, e)

            time.sleep(retry_delay)

        logger.error(
            "Failed to connect and create channel after %d attempts",
            max_retries)
        return False

    def setup_infrastructure(self) -> None:
        """
        Set up the RabbitMQ infrastructure (exchanges, queues, bindings).
        """
        exchanges: Dict[str, str] = self.config.get('exchanges', {})
        queue_config: Dict[str, Any] = self.config.get('queue', {})

        try:
            # Input exchange to receive commands
            input_exchange: str = exchanges.get('input', 'ex.bridge.output')
            self.channel.exchange_declare(
                exchange=input_exchange,
                exchange_type='topic',
                durable=True
            )
            logger.debug("Declared input exchange: %s", input_exchange)

            # Output exchange to send results
            output_exchange: str = exchanges.get('output', 'ex.sim.result')
            self.channel.exchange_declare(
                exchange=output_exchange,
                exchange_type='topic',
                durable=True
            )
            logger.debug("Declared output exchange: %s", output_exchange)

            # Queue for receiving input messages
            self.channel.queue_declare(
                queue=self.input_queue_name,
                durable=queue_config.get('durable', True)
            )

            # Bind queue to input exchange
            self.channel.queue_bind(
                exchange=input_exchange,
                queue=self.input_queue_name,
                # Accept messages from any source to this agent
                routing_key=f"*.{self.agent_id}"
            )
            logger.debug(
                "Declared and bound input queue: %s", self.input_queue_name)

            # Set QoS (prefetch count)
            self.channel.basic_qos(
                prefetch_count=queue_config.get('prefetch_count', 1)
            )
        except pika.exceptions.ChannelClosedByBroker as e:
            logger.error(
                "Channel closed by broker while setting up infrastructure: %s", e)
            sys.exit(1)

    def register_message_handler(
        self,
        handler_func: Callable[
            [pika.adapters.blocking_connection.BlockingChannel,
             pika.spec.Basic.Deliver,
             BasicProperties,
             bytes],
            None]
    ) -> None:
        """
        Register a function to handle incoming messages.

        Args:
            handler_func (callable): Function to handle messages
        """
        self.message_handler = handler_func

    def start_consuming(self) -> None:
        """
        Start consuming messages from the input queue.
        """
        if not self.message_handler:
            logger.error(
                "No message handler registered. Cannot start consuming.")
            return

        if not self.channel or not self.channel.is_open:
            logger.error(
                "Channel is not initialized. Attempting to reconnect...")
            self.connect()
            if not self.channel:
                logger.error(
                    "Failed to initialize channel after reconnecting.")
                return

        try:
            self.channel.basic_consume(
                queue=self.input_queue_name,
                on_message_callback=self.message_handler
            )
            logger.debug(
                "Started consuming messages from queue: %s",
                self.input_queue_name)
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info(
                "Stopping message consumption due to keyboard interrupt")
            if self.channel:
                self.channel.stop_consuming()
        except pika.exceptions.AMQPError as e:
            logger.error("Error while consuming messages: %s", e)
            self.close()

    def send_message(
        self,
        exchange: str,
        routing_key: str,
        body: str,
        properties: Optional[BasicProperties] = None
    ) -> bool:
        """
        Send a message to a specified exchange with a routing key.

        Args:
            exchange (str): The exchange to publish to
            routing_key (str): The routing key for the message
            body (str): The message body
            properties (pika.BasicProperties, optional): Message properties

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=body,
                properties=properties or pika.BasicProperties(
                    delivery_mode=2  # Persistent message
                )
            )
            logger.debug(
                "Sent message to exchange %s with routing key %s",
                exchange,
                routing_key)
            return True
        except pika.exceptions.AMQPError as e:
            logger.error("Failed to send message: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            return False

    def send_result(self, destination: str, result: Dict[str, Any]) -> bool:
        """
        Send simulation results to the specified destination.

        Args:
            destination (str): Destination identifier (e.g., 'dt', 'pt')
            result (dict): Result data to be sent

        Returns:
            bool: True if successful, False otherwise
        """
        exchanges: Dict[str, str] = self.config.get('exchanges', {})
        output_exchange: str = exchanges.get('output', 'ex.sim.result')

        # Prepare the payload with the destination
        payload: Dict[str, Any] = {
            **result,  # Result data
            'source': self.agent_id,  # Agent identifier
            'destinations': [destination]  # Recipient
        }

        # Generate message ID
        message_id: str = str(uuid.uuid4())

        # Serialize to YAML
        payload_yaml: str = yaml.dump(payload, default_flow_style=False)

        # Routing key: <source>.result.<destination>
        routing_key: str = f"{self.agent_id}.result.{destination}"

        properties: BasicProperties = pika.BasicProperties(
            delivery_mode=2,  # Persistent message
            content_type='application/x-yaml',
            message_id=message_id
        )

        success: bool = self.send_message(
            output_exchange, routing_key, payload_yaml, properties)

        if success:
            logger.debug(
                "Sent result to %s with message ID: %s and payload: %s",
                destination,
                message_id,
                payload)
        else:
            logger.error("Failed to send result to %s", destination)

        return success

    def close(self) -> None:
        """
        Close the RabbitMQ connection.
        """
        if self.channel and self.channel.is_open:
            try:
                self.channel.stop_consuming()
            except pika.exceptions.AMQPError:
                pass
            logger.debug("Stopped consuming messages")

        if self.connection and self.connection.is_open:
            self.connection.close()
            logger.info("Closed RabbitMQ connection")
