"""Tests for shared RabbitMQ manager."""

from unittest.mock import Mock

from base_agent.comm.rabbitmq.rabbitmq_manager import RabbitMQManager


def test_send_result_uses_yaml_module():
    """Result publishing should use injected yaml module and broker send path."""
    logger = Mock()
    pika_module = Mock()
    yaml_module = Mock()
    yaml_module.dump.return_value = "serialized"

    manager = RabbitMQManager(
        agent_id="agent",
        config={"exchanges": {"output": "ex.sim.result"}},
        logger=logger,
        pika_module=pika_module,
        yaml_module=yaml_module,
    )
    manager.send_message = Mock(return_value=True)

    assert manager.send_result("dt", {"k": "v"}) is True
    yaml_module.dump.assert_called_once()
    manager.send_message.assert_called_once()
