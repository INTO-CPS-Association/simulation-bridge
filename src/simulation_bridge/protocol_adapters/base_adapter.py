from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseProtocolAdapter(ABC):
    @property
    @abstractmethod
    def default_format(self) -> str:
        """Return default data format for this adapter"""
        pass

    @abstractmethod
    async def connect(self):
        """Connect to the protocol endpoint"""
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from the protocol endpoint"""
        pass

    @abstractmethod
    async def send(self, data: Dict[str, Any]):
        """Send data through the adapter"""
        pass

    @abstractmethod
    async def receive(self) -> Dict[str, Any]:
        """Receive data from the adapter"""
        pass