# core.py - Base components for message routing
from typing import List, Dict, Any
import pika
from .utils.logger import get_logger

class RabbitMQConnection:
    def __init__(self, host: str = 'localhost') -> None:
        self.connection_params: pika.ConnectionParameters = pika.ConnectionParameters(host)
        self.connection: pika.BlockingConnection | None = None
        self.channel: pika.adapters.blocking_connection.BlockingChannel | None = None
    
    def connect(self) -> pika.adapters.blocking_connection.BlockingChannel:
        """Establish a connection to RabbitMQ and return the channel."""
        self.connection = pika.BlockingConnection(self.connection_params)
        self.channel = self.connection.channel()
        return self.channel
    
    def close(self) -> None:
        """Close the RabbitMQ connection if it is open."""
        if self.connection and self.connection.is_open:
            self.connection.close()

class InfrastructureManager:
    def __init__(self, channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
        self.channel: pika.adapters.blocking_connection.BlockingChannel = channel
        self.logger = get_logger()

    def setup_exchanges(self, exchanges: List[Dict[str, Any]]) -> None:
        """Declare exchanges based on the provided configuration."""
        for exchange in exchanges:
            self.channel.exchange_declare(
                exchange=exchange['name'],
                exchange_type=exchange['type'],
                durable=exchange['durable']
            )
            self.logger.debug(
                "Declared exchange: %s (type: %s, durable: %s)",
                exchange['name'],
                exchange['type'],
                exchange['durable']
            )

    def setup_queues(self, queues: List[Dict[str, Any]]) -> None:
        """Declare queues based on the provided configuration."""
        for queue in queues:
            self.channel.queue_declare(
                queue=queue['name'],
                durable=queue['durable']
            )
            self.logger.debug(
                "Declared queue: %s (durable: %s)",
                queue['name'],
                queue['durable']
            )

    def setup_bindings(self, bindings: List[Dict[str, Any]]) -> None:
        """Create bindings between queues and exchanges."""
        for binding in bindings:
            self.channel.queue_bind(
                queue=binding['queue'],
                exchange=binding['exchange'],
                routing_key=binding['routing_key']
            )
            self.logger.debug(
                "Created binding: %s -> %s (%s)",
                binding['queue'],
                binding['exchange'],
                binding['routing_key']
            )

class BaseMessageHandler:
    def __init__(self, channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
        self.channel: pika.adapters.blocking_connection.BlockingChannel = channel
    
    def handle(self, ch: pika.adapters.blocking_connection.BlockingChannel, 
               method: pika.spec.Basic.Deliver, 
               properties: pika.spec.BasicProperties, 
               body: bytes) -> None:
        """Handle incoming messages. Must be implemented by subclasses."""
        raise NotImplementedError("Must be implemented by subclasses")

    def ack_message(self, ch: pika.adapters.blocking_connection.BlockingChannel, delivery_tag: int) -> None:
        """Acknowledge the message."""
        ch.basic_ack(delivery_tag)
    
    def nack_message(self, ch: pika.adapters.blocking_connection.BlockingChannel, delivery_tag: int) -> None:
        """Negatively acknowledge the message."""
        ch.basic_nack(delivery_tag)