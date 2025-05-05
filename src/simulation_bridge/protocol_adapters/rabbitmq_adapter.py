import asyncio
import pika
import yaml
from typing import Dict, Any, Optional
from pika.adapters import asyncio_connection
from ..utils.logger import get_logger

logger = get_logger(__name__)

class RabbitMQAdapter:
    def __init__(self, config: Dict[str, Any]):
        self.connection_params = pika.ConnectionParameters(
            host=config.get('host', 'localhost'),
            port=config.get('port', 5672),
            credentials=config.get('credentials', pika.PlainCredentials('guest', 'guest'))
        )
        self.exchange = config.get('exchange', 'simulation_exchange')
        self.exchange_type = config.get('exchange_type', 'topic')
        self.routing_key = config.get('routing_key', 'simulation.events')
        self.connection = None
        self.channel = None
        self.message_queue = asyncio.Queue()  # For handling incoming messages

    async def connect(self):
        """Establishes an asynchronous connection to RabbitMQ."""
        try:
            # Using AsyncioConnection for async behavior
            self.connection = pika.adapters.asyncio_connection.AsyncioConnection(self.connection_params, self.on_connection_open)
            logger.info(f"Connecting to RabbitMQ exchange: {self.exchange}")
            await self._wait_for_connection()
        except Exception as e:
            logger.error(f"RabbitMQ connection failed: {str(e)}")
            raise

    async def _wait_for_connection(self):
        """Ensure the connection is fully established."""
        while not self.connection.is_open:
            await asyncio.sleep(0.1)

    def on_connection_open(self, connection):
        """Callback when the connection is open."""
        connection.channel(self.on_channel_open)

    def on_channel_open(self, channel):
        """Callback when the channel is open."""
        self.channel = channel
        logger.info(f"Channel {channel} opened successfully.")
        self.channel.exchange_declare(
            exchange=self.exchange,
            exchange_type=self.exchange_type,
            durable=True,
            callback=self.on_exchange_declareok
        )

    def on_exchange_declareok(self, _):
        """Callback after the exchange is declared."""
        logger.info(f"Exchange {self.exchange} declared successfully.")
        self._start_consuming()

    def _start_consuming(self):
        """Start consuming messages."""
        try:
            result = self.channel.queue_declare(queue='', exclusive=True)
            queue_name = result.method.queue
            self.channel.queue_bind(
                exchange=self.exchange,
                queue=queue_name,
                routing_key=self.routing_key
            )

            # Start consuming with a callback
            self.channel.basic_consume(queue=queue_name, on_message_callback=self.on_message, auto_ack=False)
            logger.info(f"Waiting for messages on queue: {queue_name}")
            self.channel.start_consuming()

        except Exception as e:
            logger.error(f"Failed to start consuming: {str(e)}")
            raise

    def on_message(self, ch, method, properties, body):
        """Callback for handling incoming messages."""
        try:
            message = yaml.safe_load(body)
            logger.debug(f"Received message: {message}")
            ch.basic_ack(method.delivery_tag)  # Acknowledge the message
            asyncio.run(self.message_queue.put(message))  # Put the message in the asyncio Queue
        except Exception as e:
            logger.error(f"Failed to process message: {str(e)}")

    async def receive(self) -> Optional[Dict[str, Any]]:
        """Async method to receive messages from the queue."""
        try:
            message = await self.message_queue.get()
            logger.debug(f"Received message from queue: {message}")
            return message
        except Exception as e:
            logger.error(f"Failed to receive message: {str(e)}")
            return None

    async def send(self, message: Dict[str, Any]):
        """Publish a message to the exchange."""
        try:
            if not self.channel or not self.connection.is_open:
                logger.error("No open channel or connection. Cannot send message.")
                return

            self.channel.basic_publish(
                exchange=self.exchange,
                routing_key=self.routing_key,
                body=yaml.dump(message),
                properties=pika.BasicProperties(
                    delivery_mode=2  # Make message persistent
                )
            )
            logger.debug(f"Sent message to {self.exchange}: {message}")
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            raise

    def close(self):
        """Close the RabbitMQ connection and channel."""
        try:
            if self.channel:
                self.channel.close()
            if self.connection:
                self.connection.close()
            logger.info("RabbitMQ connection closed.")
        except Exception as e:
            logger.error(f"Failed to close RabbitMQ connection: {str(e)}")
