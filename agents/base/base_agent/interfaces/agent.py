"""Common agent interface for simulator implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class IAgent(ABC):
    """Interface for agents that consume requests and publish simulation results."""

    @abstractmethod
    def __init__(self, agent_id: str, config_path: Optional[str] = None) -> None:
        """Initialize an agent with an ID and optional configuration path."""

    @abstractmethod
    def start(self) -> None:
        """Start consuming and handling simulation requests."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the agent and release external resources."""

    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """Return the loaded runtime configuration."""
