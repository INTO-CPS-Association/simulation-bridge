"""Module providing the abstract base class for protocol adapters."""

from abc import ABC, abstractmethod
from typing import Dict, Any
from ...utils.config_manager import ConfigManager
from ...utils.logger import get_logger

logger = get_logger()


class ProtocolAdapter(ABC):
    """
    Abstract base class that defines the interface and common behavior
    for all protocol adapters.

    Subclasses must implement configuration loading, start/stop lifecycle,
    and message handling methods.
    """

    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the protocol adapter.

        Args:
            config_manager (ConfigManager): Configuration manager instance
        """
        self.config_manager = config_manager
        self.config = self._get_config()
        self._running = False
        logger.debug(
            "%s - Adapter initialized with config: %s",
            self.__class__.__name__,
            self.config)

    @property
    def is_running(self) -> bool:
        """
        Indicates whether the adapter is currently running.

        Returns:
            bool: True if running, False otherwise
        """
        return self._running

    @abstractmethod
    def _get_config(self) -> Dict[str, Any]:
        """
        Retrieve protocol-specific configuration.

        Returns:
            Dict[str, Any]: Configuration dictionary
        """

    @abstractmethod
    def start(self) -> None:
        """
        Start the protocol adapter.
        Should initiate connections, threads, or other resources.
        """

    @abstractmethod
    def stop(self) -> None:
        """
        Stop the protocol adapter.
        Should cleanly release resources and stop threads.
        """

    @abstractmethod
    def _handle_message(self, message: Dict[str, Any]) -> None:
        """
        Handle an incoming message according to the protocol logic.

        Args:
            message (Dict[str, Any]): The message to handle
        """
