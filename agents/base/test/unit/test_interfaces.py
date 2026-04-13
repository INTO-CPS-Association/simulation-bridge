"""Tests for shared interface exports."""

from base_agent.comm.interfaces import IMessageBroker, IMessageHandler
from base_agent.comm.rabbitmq.interfaces import IRabbitMQManager, IRabbitMQMessageHandler
from base_agent.interfaces.config_manager import IConfigManager


def test_interface_symbols_are_importable():
    """Smoke test: all shared interface symbols are exported."""
    assert IMessageBroker is not None
    assert IMessageHandler is not None
    assert IRabbitMQManager is not None
    assert IRabbitMQMessageHandler is not None
    assert IConfigManager is not None
