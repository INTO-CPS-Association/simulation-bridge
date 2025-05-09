"""
Interface for managing RabbitMQ connections, exchanges, queues, and message handling.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional
import pika
from pika.spec import BasicProperties

class IRabbitMQManager(ABC):
    """
    Interface for managing RabbitMQ connections, exchanges, queues, and message handling.
    """
    @abstractmethod
    def connect(self) -> None:
        """
        Establish a connection to RabbitMQ using configuration parameters.
        """
    @abstractmethod
    def setup_infrastructure(self) -> None:
        """
        Set up RabbitMQ infrastructure (exchanges, queues, bindings).
        """
    @abstractmethod
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
            handler_func (callable): Function to handle messages.
        """
    @abstractmethod
    def start_consuming(self) -> None:
        """
        Start consuming messages from the input queue.
        """
    @abstractmethod
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
            exchange (str): The exchange to publish to.
            routing_key (str): The routing key for the message.
            body (str): The message body.
            properties (pika.BasicProperties, optional): Message properties.

        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
    @abstractmethod
    def send_result(self, destination: str, result: Dict[str, Any]) -> bool:
        """
        Send simulation results to the specified destination.

        Args:
            destination (str): The destination identifier (e.g., 'dt', 'pt').
            result (dict): The result data to be sent.

        Returns:
            bool: True if the result was sent successfully, False otherwise.
        """
    @abstractmethod
    def close(self) -> None:
        """
        Close the RabbitMQ connection.
        """
