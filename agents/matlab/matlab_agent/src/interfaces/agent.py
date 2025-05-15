"""
This module defines the `IMatlabAgent` interface.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict


class IMatlabAgent(ABC):
    """
    Interface for MATLAB Agent that handles message reception, processing,
    and result distribution via RabbitMQ.
    """
    @abstractmethod
    def __init__(self, agent_id: str, config_path: str = None) -> None:
        """
        Initialize the MATLAB agent with the specified ID, and optionally a configuration file.

        Args:
            agent_id (str): The ID of the agent
            config_path (str, optional): The path to the configuration file
        """
    @abstractmethod
    def start(self) -> None:
        """
        Start consuming messages from the input queue.
        """
    @abstractmethod
    def stop(self) -> None:
        """
        Stop the agent and close connections.
        """
    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """
        Retrieve the agent's configuration as a dictionary.

        Returns:
            Dict[str, Any]: The agent's configuration
        """
