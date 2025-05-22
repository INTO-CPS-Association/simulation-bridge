"""
Base message handler for RabbitMQ messages.
"""
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties

class BaseMessageHandler:
    def __init__(self, channel: BlockingChannel) -> None:
        self.channel: BlockingChannel = channel

    def handle(self, ch: BlockingChannel,
               method: Basic.Deliver,
               properties: BasicProperties,
               body: bytes) -> None:
        """Handle incoming messages. Must be implemented by subclasses."""
        raise NotImplementedError("Must be implemented by subclasses")

    def ack_message(self, ch: BlockingChannel, delivery_tag: int) -> None:
        """Acknowledge the message."""
        ch.basic_ack(delivery_tag)

    def nack_message(self, ch: BlockingChannel, delivery_tag: int) -> None:
        """Negatively acknowledge the message."""
        ch.basic_nack(delivery_tag)
