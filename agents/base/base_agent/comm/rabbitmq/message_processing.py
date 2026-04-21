"""Shared helpers for RabbitMQ message parsing and validation."""

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class SimulationMessageContext:
    """Metadata extracted from a simulation payload."""

    sim_file: str = ""
    sim_type: str = ""
    bridge_meta: Any = "unknown"
    request_id: str = "unknown"


def extract_source_from_routing_key(routing_key: str) -> str:
    """Return the source prefix from a RabbitMQ routing key."""
    return routing_key.split(".")[0]


def parse_message_body(
    body: bytes,
    parser: Callable[[bytes], Any],
    logger: Any,
) -> Any:
    """Parse a raw message body using the provided parser callback."""
    parsed_message = parser(body)
    logger.debug("Parsed message: %s", parsed_message)
    return parsed_message


def extract_context_from_message(msg_dict: Any) -> SimulationMessageContext:
    """Extract simulation metadata from a parsed message dictionary."""
    context = SimulationMessageContext()
    if isinstance(msg_dict, dict) and "simulation" in msg_dict:
        sim_data = msg_dict["simulation"]
        context.sim_file = sim_data.get("file", "")
        context.sim_type = sim_data.get("type", "")
        context.bridge_meta = sim_data.get("bridge_meta", "unknown")
        context.request_id = sim_data.get("request_id", "unknown")
    return context


def validate_message_payload(
    msg_dict: Any,
    payload_factory: Callable[[Any], Any],
    logger: Any,
) -> tuple[Optional[Any], SimulationMessageContext, Optional[str]]:
    """Validate payload and extract normalized simulation context."""
    try:
        payload = payload_factory(msg_dict)
        logger.debug("Message validation successful")
        simulation_data = payload.simulation
        context = SimulationMessageContext(
            sim_file=simulation_data.file,
            sim_type=simulation_data.type,
            bridge_meta=simulation_data.bridge_meta or "unknown",
            request_id=simulation_data.request_id,
        )
        return payload, context, None
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Message validation failed: %s", exc)
        return None, extract_context_from_message(msg_dict), str(exc)


def build_error_response(
    response_builder: Callable[..., Any],
    context: SimulationMessageContext,
    error: dict[str, Any],
) -> Any:
    """Build a standardized error response from the provided context."""
    return response_builder(
        template_type="error",
        sim_file=context.sim_file,
        sim_type=context.sim_type,
        response_templates={},
        bridge_meta=context.bridge_meta,
        request_id=context.request_id,
        error=error,
    )
