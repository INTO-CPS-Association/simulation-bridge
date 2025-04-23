from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseConnector(ABC):
    @abstractmethod
    async def initialize(self):
        """Initialize connection to simulator."""
        pass