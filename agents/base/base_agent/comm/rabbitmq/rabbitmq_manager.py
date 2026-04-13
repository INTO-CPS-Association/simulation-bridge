"""Shared RabbitMQ manager for simulation agents."""

import ssl
import time
import uuid
from typing import Any, Callable, Dict, Optional

import pika
import yaml
from pika.spec import BasicProperties

from .interfaces import IRabbitMQManager


class RabbitMQManager(IRabbitMQManager):
    """Manager for RabbitMQ connection lifecycle and message I/O."""

    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-instance-attributes
    def __init__(
        self,
        agent_id: str,
        config: Dict[str, Any],
        logger: Any,
        pika_module: Any = pika,
        yaml_module: Any = yaml,
    ) -> None:
        self.agent_id = agent_id
        self.config = config
        self.logger = logger
        self.pika = pika_module
        self.yaml = yaml_module
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        self.input_queue_name = f"Q.sim.{self.agent_id}"
        self.message_handler: Optional[
            Callable[
                [
                    pika.adapters.blocking_connection.BlockingChannel,
                    pika.spec.Basic.Deliver,
                    BasicProperties,
                    bytes,
                ],
                None,
            ]
        ] = None

    def connect(self) -> bool:
        """Connect to RabbitMQ and open a channel with retries."""
        rabbitmq_config = self.config.get("rabbitmq", {})
        max_retries = 5
        retry_delay = 2

        for attempt in range(1, max_retries + 1):
            try:
                self.logger.debug("Connecting to RabbitMQ (attempt %d)...", attempt)
                credentials = self.pika.PlainCredentials(
                    rabbitmq_config.get("username", "guest"),
                    rabbitmq_config.get("password", "guest"),
                )
                vhost = rabbitmq_config.get("vhost", "/")
                self.logger.debug("Using vhost: %s", vhost)
                use_tls = rabbitmq_config.get("tls", False)

                if use_tls:
                    context = ssl.create_default_context()
                    context.minimum_version = ssl.TLSVersion.TLSv1_2
                    ssl_options = self.pika.SSLOptions(
                        context,
                        rabbitmq_config.get("host", "localhost"),
                    )
                    parameters = self.pika.ConnectionParameters(
                        host=rabbitmq_config.get("host", "localhost"),
                        port=rabbitmq_config.get("port", 5671),
                        virtual_host=vhost,
                        credentials=credentials,
                        ssl_options=ssl_options,
                        heartbeat=rabbitmq_config.get("heartbeat", 600),
                    )
                else:
                    parameters = self.pika.ConnectionParameters(
                        host=rabbitmq_config.get("host", "localhost"),
                        port=rabbitmq_config.get("port", 5672),
                        virtual_host=vhost,
                        credentials=credentials,
                        heartbeat=rabbitmq_config.get("heartbeat", 600),
                    )

                self.connection = self.pika.BlockingConnection(parameters)
                if self.connection.is_open:
                    self.logger.debug(
                        "Connection to RabbitMQ is open. Attempting to create channel..."
                    )
                    self.channel = self.connection.channel()
                    if self.channel and self.channel.is_open:
                        self.logger.debug(
                            "Successfully connected to RabbitMQ and channel is open."
                        )
                        return True
                    self.logger.error("Channel creation failed. Retrying...")
                self.logger.error(
                    "Connection opened but channel could not be created. Retrying..."
                )
            except self.pika.exceptions.AMQPConnectionError as error:
                self.logger.error(
                    "Connection failed (attempt %d) to %s:%s vhost=%s — %s: %r",
                    attempt,
                    rabbitmq_config.get("host"),
                    rabbitmq_config.get("port"),
                    rabbitmq_config.get("vhost", "/"),
                    error.__class__.__name__,
                    error,
                )
            time.sleep(retry_delay)

        self.logger.error(
            "Failed to connect and create channel after %d attempts",
            max_retries,
        )
        return False

    def setup_infrastructure(self) -> None:
        """Declare exchanges, queue, bindings, and QoS."""
        if not self.channel or not self.channel.is_open:
            self.logger.error("Channel is not available.")
            raise RuntimeError("Channel is not available.")

        exchanges = self.config.get("exchanges", {})
        queue_config = self.config.get("queue", {})

        try:
            input_exchange = exchanges.get("input", "ex.bridge.output")
            self.channel.exchange_declare(
                exchange=input_exchange,
                exchange_type="topic",
                durable=True,
            )
            self.logger.debug("Declared input exchange: %s", input_exchange)

            output_exchange = exchanges.get("output", "ex.sim.result")
            self.channel.exchange_declare(
                exchange=output_exchange,
                exchange_type="topic",
                durable=True,
            )
            self.logger.debug("Declared output exchange: %s", output_exchange)

            self.channel.queue_declare(
                queue=self.input_queue_name,
                durable=queue_config.get("durable", True),
            )
            self.channel.queue_bind(
                exchange=input_exchange,
                queue=self.input_queue_name,
                routing_key=f"*.{self.agent_id}",
            )
            self.logger.debug("Declared and bound input queue: %s", self.input_queue_name)
            self.channel.basic_qos(prefetch_count=queue_config.get("prefetch_count", 1))
        except self.pika.exceptions.ChannelClosedByBroker as error:
            self.logger.error(
                "Channel closed by broker while setting up infrastructure: %s",
                error,
            )
            raise RuntimeError(
                "Channel closed by broker while setting up infrastructure."
            ) from error

    def register_message_handler(
        self,
        handler_func: Callable[
            [
                pika.adapters.blocking_connection.BlockingChannel,
                pika.spec.Basic.Deliver,
                BasicProperties,
                bytes,
            ],
            None,
        ],
    ) -> None:
        """Register incoming-message callback."""
        self.message_handler = handler_func

    def start_consuming(self) -> None:
        """Start consuming from input queue."""
        if not self.message_handler:
            self.logger.error("No message handler registered. Cannot start consuming.")
            return

        if not self.channel or not self.channel.is_open:
            self.logger.error("Channel is not initialized. Attempting to reconnect...")
            self.connect()
            if not self.channel:
                self.logger.error("Failed to initialize channel after reconnecting.")
                return

        try:
            self.channel.basic_consume(
                queue=self.input_queue_name,
                on_message_callback=self.message_handler,
            )
            self.logger.debug("Started consuming messages from queue: %s", self.input_queue_name)
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.logger.info("Stopping message consumption due to keyboard interrupt")
            if self.channel:
                self.channel.stop_consuming()
        except self.pika.exceptions.AMQPError as error:
            self.logger.error("Error while consuming messages: %s", error)
            self.close()

    def send_message(
        self,
        exchange: str,
        routing_key: str,
        body: str,
        properties: Optional[BasicProperties] = None,
    ) -> bool:
        """Publish a message to exchange/routing key."""
        try:
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=body,
                properties=properties or self.pika.BasicProperties(delivery_mode=2),
            )
            self.logger.debug(
                "Sent message to exchange %s with routing key %s",
                exchange,
                routing_key,
            )
            return True
        except self.pika.exceptions.AMQPError as error:
            self.logger.error("Failed to send message: %s", error)
            return False
        except Exception as error:  # pylint: disable=broad-exception-caught
            self.logger.error("Unexpected error: %s", error)
            return False

    def send_result(self, destination: str, result: Dict[str, Any]) -> bool:
        """Publish simulation result payload to output exchange."""
        output_exchange = self.config.get("exchanges", {}).get(
            "output",
            "ex.sim.result",
        )
        payload = {
            **result,
            "source": self.agent_id,
            "destinations": [destination],
        }
        message_id = str(uuid.uuid4())
        payload_yaml = self.yaml.dump(payload, default_flow_style=False)
        routing_key = f"{self.agent_id}.result.{destination}"

        properties = self.pika.BasicProperties(
            delivery_mode=2,
            content_type="application/x-yaml",
            message_id=message_id,
        )
        success = self.send_message(
            output_exchange,
            routing_key,
            payload_yaml,
            properties,
        )

        if success:
            self.logger.debug(
                "Sent result to %s with message ID: %s and payload: %s",
                destination,
                message_id,
                payload,
            )
        else:
            self.logger.error("Failed to send result to %s", destination)

        return success

    def close(self) -> None:
        """Close channel consumption and connection."""
        if self.channel and self.channel.is_open:
            try:
                self.channel.stop_consuming()
            except self.pika.exceptions.AMQPError:
                pass
            self.logger.debug("Stopped consuming messages")

        if self.connection and self.connection.is_open:
            self.connection.close()
            self.logger.info("Closed RabbitMQ connection")
