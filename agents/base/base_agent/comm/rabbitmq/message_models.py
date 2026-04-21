"""Shared Pydantic models for simulator RabbitMQ payload validation."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _format_allowed_types(allowed_types: tuple[str, ...]) -> str:
    """Return a human-readable list of quoted simulation types."""
    quoted_types = [f"'{simulation_type}'" for simulation_type in allowed_types]
    if len(quoted_types) == 1:
        return quoted_types[0]
    if len(quoted_types) == 2:
        return f"{quoted_types[0]} or {quoted_types[1]}"
    return f"{', '.join(quoted_types[:-1])} or {quoted_types[-1]}"


class SimulationInputs(BaseModel):
    """Base model for dynamic simulation input payloads."""

    stream_source: str | None = None
    model_config = ConfigDict(extra="allow")


class SimulationOutputs(BaseModel):
    """Base model for dynamic simulation output payloads."""

    model_config = ConfigDict(extra="allow")


class BaseSimulationData(BaseModel):
    """Shared simulation data model with overridable type constraints."""

    allowed_simulation_types: ClassVar[tuple[str, ...]] = ("batch", "streaming")
    stream_source_required_types: ClassVar[tuple[str, ...]] = ()

    request_id: str
    client_id: str
    simulator: str
    type: str = Field(default="batch")
    file: str
    inputs: SimulationInputs
    outputs: Optional[SimulationOutputs] = None
    bridge_meta: Optional[Dict[str, Any]] = None

    @field_validator("type", mode="before")
    @classmethod
    def validate_sim_type(cls, value: Any) -> Any:
        """Validate that the simulation type is among configured allowed values."""
        if value not in cls.allowed_simulation_types:
            raise ValueError(
                f"Invalid simulation type: {value}. Must be "
                f"{_format_allowed_types(cls.allowed_simulation_types)}"
            )
        return value

    @model_validator(mode="after")
    def check_stream_source_for_required_types(self):
        """Validate stream_source requirement for configured simulation types."""
        if (
            self.type in self.stream_source_required_types
            and not self.inputs.stream_source
        ):
            raise ValueError(
                f"For '{self.type}' simulations you must provide "
                "'inputs.stream_source'"
            )
        return self


class BaseMessagePayload(BaseModel):
    """Shared top-level payload model used by RabbitMQ handlers."""

    simulation: BaseSimulationData
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


__all__ = [
    "SimulationInputs",
    "SimulationOutputs",
    "BaseSimulationData",
    "BaseMessagePayload",
]
