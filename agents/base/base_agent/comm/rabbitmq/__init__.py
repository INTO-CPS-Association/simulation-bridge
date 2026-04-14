"""Shared RabbitMQ communication interfaces."""

from .interfaces import IRabbitMQManager, IRabbitMQMessageHandler
from .message_processing import (
    SimulationMessageContext,
    build_error_response,
    extract_context_from_message,
    extract_source_from_routing_key,
    parse_message_body,
    validate_message_payload,
)
from .rabbitmq_manager import RabbitMQManager

__all__ = [
    "IRabbitMQManager",
    "IRabbitMQMessageHandler",
    "RabbitMQManager",
    "SimulationMessageContext",
    "build_error_response",
    "extract_context_from_message",
    "extract_source_from_routing_key",
    "parse_message_body",
    "validate_message_payload",
]
