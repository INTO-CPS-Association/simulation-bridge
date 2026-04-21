"""
Defines the generic IMessageBroker interface for communication.
This module provides the base interface that all communication implementations should follow,
enabling easy substitution of different messaging technologies.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Callable, Optional


class IMessageBroker(ABC):
    """
    Interface for a message broker that handles communication between components.
    This abstraction allows for swapping different messaging technologies (RabbitMQ, Kafka, etc.)
    without changing the core application logic.
    """

    @abstractmethod
    def connect(self) -> None:
        """
        Establish a connection to the message broker.
        """

    @abstractmethod
    def setup_infrastructure(self) -> None:
        """
        Set up required infrastructure (exchanges, queues, topics, etc.).
        """

    @abstractmethod
    def register_message_handler(self, handler_func: Callable) -> None:
        """
        Register a function to handle incoming messages.

        Args:
            handler_func: A callback function that processes incoming messages
        """

    @abstractmethod
    def start_consuming(self) -> None:
        """
        Start consuming messages from the input channel.
        """

    @abstractmethod
    def send_message(
            self,
            exchange: str,
            routing_key: str,
            body: Any,
            properties: Optional[Any] = None) -> bool:
        """
        Send a message to a specified destination.

        Args:
            exchange: The exchange to publish to
            routing_key: The routing key for the message
            body: The message body
            properties: Message properties

        Returns:
            bool: True if successful, False otherwise
        """

    @abstractmethod
    def send_result(self, destination: str, result: Dict[str, Any]) -> bool:
        """
        Send operation results to the specified destination.

        Args:
            destination: The destination identifier
            result: The result data to be sent

        Returns:
            bool: True if successful, False otherwise
        """

    @abstractmethod
    def close(self) -> None:
        """
        Close the connection to the message broker.
        """


class IMessageHandler(ABC):
    """
    Interface for handling messages received from a message broker.
    """

    @abstractmethod
    def handle_message(self, *args, **kwargs) -> None:
        """
        Process incoming messages from the message broker.

        Args:
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
        """

    @abstractmethod
    def get_agent_id(self) -> str:
        """
        Retrieve the agent ID.

        Returns:
            str: The ID of the agent
        """
