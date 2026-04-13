"""Tests for shared connect wrapper."""

from unittest.mock import Mock

import pytest

from base_agent.comm.connect import Connect


@pytest.fixture
def mock_config():
    return {"exchanges": {"output": "ex.sim.result"}}


def test_connect_initializes_rabbitmq(mock_config):
    broker = Mock()
    handler = Mock()
    connect = Connect(
        agent_id="agent",
        config=mock_config,
        broker_type="rabbitmq",
        broker_factory=Mock(return_value=broker),
        message_handler_factory=Mock(return_value=handler),
        logger=Mock(),
    )
    assert connect.broker is broker
    assert connect.message_handler is handler


def test_connect_rejects_unsupported_broker(mock_config):
    with pytest.raises(ValueError):
        Connect(
            agent_id="agent",
            config=mock_config,
            broker_type="kafka",
            broker_factory=Mock(),
            message_handler_factory=Mock(),
            logger=Mock(),
        )


def test_send_message_uses_defaults(mock_config):
    broker = Mock()
    broker.send_message.return_value = True
    connect = Connect(
        agent_id="agent",
        config=mock_config,
        broker_type="rabbitmq",
        broker_factory=Mock(return_value=broker),
        message_handler_factory=Mock(return_value=Mock()),
        logger=Mock(),
    )
    assert connect.send_message("dest", {"k": "v"}) is True
    broker.send_message.assert_called_once_with(
        "ex.sim.result",
        "agent.dest",
        {"k": "v"},
        None,
    )
