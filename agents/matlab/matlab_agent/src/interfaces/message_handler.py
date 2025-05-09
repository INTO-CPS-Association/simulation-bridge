"""
This module defines the `IMessageHandler` interface.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict

class IMessageHandler(ABC):
    """
    Interface for handling incoming messages from RabbitMQ.
    """
    @abstractmethod
    def handle_message(
        self,
        ch: Any,
        method: Any,
        properties: Any,
        body: bytes
    ) -> None:
        """
        Process incoming messages from RabbitMQ.
        
        Args:
            ch (Any): Channel object
            method (Any): Delivery method
            properties (Any): Message properties
            body (bytes): Message body
        """
    @abstractmethod
    def get_agent_id(self) -> str:
        """
        Retrieve the agent ID.

        Returns:
            str: The ID of the agent
        """
    @abstractmethod
    def send_result(self, destination: str, result: Dict[str, Any]) -> None:
        """
        Send the result to the specified destination.

        Args:
            destination (str): The destination to send the result
            result (Dict[str, Any]): The result to send
        """
