from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any


class SimulationStatus(str, Enum):
    STARTED = 'started'
    STOPPED = 'stopped'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    ERROR = 'error'
    STARTING = 'starting'
    RUNNING = 'running'

class SimulationState(BaseModel):
    status: SimulationStatus
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }