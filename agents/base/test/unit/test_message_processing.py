"""Tests for shared RabbitMQ message processing helpers."""

from unittest.mock import Mock

from base_agent.comm.rabbitmq.message_processing import (
    SimulationMessageContext,
    build_error_response,
    extract_context_from_message,
    extract_source_from_routing_key,
    parse_message_body,
    validate_message_payload,
)


class _SimulationData:
    """Small helper object for validation tests."""

    def __init__(self, sim_type: str, file_name: str, bridge_meta, request_id: str):
        self.type = sim_type
        self.file = file_name
        self.bridge_meta = bridge_meta
        self.request_id = request_id


class _Payload:
    """Small helper payload object for validation tests."""

    def __init__(self, simulation):
        self.simulation = simulation


def test_extract_source_from_routing_key() -> None:
    """Source should map to first routing key segment."""
    assert extract_source_from_routing_key("dt.simul8.agent") == "dt"
    assert extract_source_from_routing_key("single") == "single"


def test_parse_message_body_uses_parser_and_logs() -> None:
    """Parser callback output should be returned and logged."""
    parser = Mock(return_value={"simulation": {"type": "batch"}})
    logger = Mock()

    parsed = parse_message_body(b"payload", parser, logger)

    assert parsed == {"simulation": {"type": "batch"}}
    parser.assert_called_once_with(b"payload")
    logger.debug.assert_called_once_with("Parsed message: %s", parsed)


def test_extract_context_from_message_with_defaults() -> None:
    """Non-dict payloads should resolve to default context."""
    assert extract_context_from_message("invalid") == SimulationMessageContext()


def test_extract_context_from_message_with_simulation_data() -> None:
    """Simulation metadata should be extracted from message dictionary."""
    context = extract_context_from_message(
        {
            "simulation": {
                "file": "model.sim",
                "type": "batch",
                "bridge_meta": {"protocol": "rabbitmq"},
                "request_id": "req-1",
            }
        }
    )

    assert context == SimulationMessageContext(
        sim_file="model.sim",
        sim_type="batch",
        bridge_meta={"protocol": "rabbitmq"},
        request_id="req-1",
    )


def test_validate_message_payload_success() -> None:
    """Successful validation should return payload and normalized context."""
    logger = Mock()
    payload_obj = _Payload(
        _SimulationData(
            sim_type="streaming",
            file_name="run.m",
            bridge_meta=None,
            request_id="req-2",
        )
    )

    payload, context, error = validate_message_payload(
        msg_dict={"simulation": {"type": "streaming"}},
        payload_factory=lambda _msg: payload_obj,
        logger=logger,
    )

    assert payload is payload_obj
    assert context == SimulationMessageContext(
        sim_file="run.m",
        sim_type="streaming",
        bridge_meta="unknown",
        request_id="req-2",
    )
    assert error is None
    logger.debug.assert_called_once_with("Message validation successful")


def test_validate_message_payload_failure_uses_fallback_context() -> None:
    """Validation failures should return fallback context and error details."""
    logger = Mock()

    def _raise_validation_error(_msg):
        raise ValueError("invalid payload")

    payload, context, error = validate_message_payload(
        msg_dict={
            "simulation": {
                "file": "fallback.sim",
                "type": "batch",
                "bridge_meta": "meta",
                "request_id": "req-3",
            }
        },
        payload_factory=_raise_validation_error,
        logger=logger,
    )

    assert payload is None
    assert context == SimulationMessageContext(
        sim_file="fallback.sim",
        sim_type="batch",
        bridge_meta="meta",
        request_id="req-3",
    )
    assert error == "invalid payload"
    logger.error.assert_called_once()


def test_build_error_response_uses_context_and_error_payload() -> None:
    """Error response builder should receive normalized fields."""
    response_builder = Mock(return_value={"status": "error"})
    context = SimulationMessageContext(
        sim_file="model.sim",
        sim_type="interactive",
        bridge_meta={"protocol": "rest"},
        request_id="req-4",
    )
    error_payload = {"message": "failure", "type": "execution_error"}

    result = build_error_response(response_builder, context, error_payload)

    assert result == {"status": "error"}
    response_builder.assert_called_once_with(
        template_type="error",
        sim_file="model.sim",
        sim_type="interactive",
        response_templates={},
        bridge_meta={"protocol": "rest"},
        request_id="req-4",
        error=error_payload,
    )
