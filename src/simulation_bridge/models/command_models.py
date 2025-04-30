from pydantic import BaseModel, Field
from typing import Literal, Dict, Any


class SimulationControlCommand(BaseModel):
    """
    Modello per i comandi di controllo della simulazione.

    Attributes:
        action: azione da eseguire (start, stop, pause, get_status)
        parameters: parametri opzionali associati al comando
    """
    action: Literal['start', 'stop', 'pause', 'get_status']
    parameters: Dict[str, Any] = Field(default_factory=dict)
