"""Pydantic models for simulation bridge message validation."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


def datetime_serializer(obj):
    """Serialize datetime objects to ISO 8601 strings."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {obj.__class__.__name__} not serializable")


class SimulationModel(BaseModel):
    """Represents the details of a simulation request."""
    request_id: str
    client_id: str
    simulator: str
    type: str
    timestamp: Optional[datetime] = None
    timeout: Optional[int] = None
    file: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    bridge_index: Optional[str] = None


class MessageModel(BaseModel):
    """Represents a message structure for simulation requests."""
    simulation: SimulationModel
