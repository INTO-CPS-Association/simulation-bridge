"""Tests for shared RabbitMQ Pydantic message models."""

import uuid
from typing import ClassVar

import pytest

from base_agent.comm.rabbitmq.message_models import (
    BaseMessagePayload,
    BaseSimulationData,
    SimulationInputs,
    SimulationOutputs,
)


class _MatlabSimulationData(BaseSimulationData):
    """Test model mirroring MATLAB simulation constraints."""

    allowed_simulation_types: ClassVar[tuple[str, ...]] = (
        "batch",
        "streaming",
        "interactive",
    )
    stream_source_required_types: ClassVar[tuple[str, ...]] = ("interactive",)


class _MatlabMessagePayload(BaseMessagePayload):
    """Test payload model using MATLAB simulation data."""

    simulation: _MatlabSimulationData


def test_simulation_inputs_and_outputs_allow_dynamic_fields() -> None:
    """Dynamic extra keys should be accepted for input and output models."""
    inputs = SimulationInputs(param1="value1", param2=2)
    outputs = SimulationOutputs(result1="output", result2=4)

    assert inputs.param1 == "value1"
    assert inputs.param2 == 2
    assert outputs.result1 == "output"
    assert outputs.result2 == 4


def test_base_simulation_data_validates_allowed_types() -> None:
    """Configured simulation type constraints should reject unsupported values."""
    with pytest.raises(
        ValueError,
        match="Invalid simulation type: invalid. Must be 'batch', 'streaming' or 'interactive'",
    ):
        _MatlabSimulationData(
            request_id="req-1",
            client_id="client-1",
            simulator="matlab",
            type="invalid",
            file="simulation.m",
            inputs=SimulationInputs(),
        )


def test_base_simulation_data_requires_stream_source_for_interactive() -> None:
    """Interactive simulations should require inputs.stream_source when configured."""
    with pytest.raises(
        ValueError,
        match="For 'interactive' simulations you must provide 'inputs.stream_source'",
    ):
        _MatlabSimulationData(
            request_id="req-1",
            client_id="client-1",
            simulator="matlab",
            type="interactive",
            file="simulation.m",
            inputs=SimulationInputs(),
        )


def test_base_message_payload_generates_request_uuid() -> None:
    """Top-level payload should generate a UUID request_id by default."""
    payload = _MatlabMessagePayload(
        simulation=_MatlabSimulationData(
            request_id="sim-req-1",
            client_id="client-1",
            simulator="matlab",
            type="batch",
            file="simulation.m",
            inputs=SimulationInputs(stream_source="ignored-for-batch"),
        )
    )

    uuid.UUID(payload.request_id)
