from abc import ABC, abstractmethod
from typing import Dict, Any
from ...utils.config_manager import ConfigManager
from ...utils.logger import get_logger

logger = get_logger()

class ProtocolAdapter(ABC):
    """
    Abstract base class that defines the interface for all protocol adapters.
    All protocol adapters must implement these methods.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the protocol adapter.
        
        Args:
            config_manager (ConfigManager): Configuration manager instance
        """
        self.config_manager = config_manager
        self.config = self._get_config()
        logger.debug(f"{self.__class__.__name__} - Adapter initialized")
    
    @abstractmethod
    def _get_config(self) -> Dict[str, Any]:
        """
        Get the specific configuration for this adapter.
        Must be implemented by each adapter.
        
        Returns:
            Dict[str, Any]: Configuration dictionary
        """
        pass
    
    @abstractmethod
    def start(self) -> None:
        """
        Start the protocol adapter.
        Must be implemented by each adapter.
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """
        Stop the protocol adapter.
        Must be implemented by each adapter.
        """
        pass
    
    @abstractmethod
    def _handle_message(self, message: Dict[str, Any]) -> None:
        """
        Handle incoming messages.
        Must be implemented by each adapter.
        
        Args:
            message (Dict[str, Any]): The message to handle
        """
        pass 