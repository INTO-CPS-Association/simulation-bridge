"""
This module defines the `IConfigManager` interface.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

class IConfigManager(ABC):
    """
    Interface for managing configuration.
    """
    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """
        Retrieve the loaded configuration as a dictionary.
        """
    @abstractmethod
    def get_default_config(self) -> Dict[str, Any]:
        """
        Retrieve the default configuration as a dictionary.
        """
    @abstractmethod
    def _validate_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the configuration using the Pydantic model.
        """
