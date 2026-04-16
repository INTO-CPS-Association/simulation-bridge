"""Unit tests for the shared Connect communication wrapper."""

from typing import Any, Dict
from unittest.mock import Mock

import pytest

from base_agent.comm.connect import (
    BROKER_CONNECTION_FAILED_ERROR,
    BROKER_NOT_INITIALIZED_ERROR,
    BROKER_OR_HANDLER_NOT_INITIALIZED_ERROR,
    Connect,
)


@pytest.fixture
def mock_config(dummy_credentials) -> Dict[str, Any]:
    """Return a minimal but valid configuration dictionary."""
    rabbit_creds = dummy_credentials.get("rabbitmq", {})
    return {
        "exchanges": {"output": "ex.sim.result", "input": "ex.sim.input"},
        "rabbitmq": {
            "host": "localhost",
            "port": 5672,
            "username": rabbit_creds.get("username", "guest"),
            "password": rabbit_creds.get("password", "guest"),
        },
    }


@pytest.fixture
def mock_logger() -> Mock:
    """Return a mocked logger instance."""
    return Mock()


@pytest.fixture
def mock_broker() -> Mock:
    """Return a fully mocked broker implementation."""
    broker = Mock()
    broker.connect.return_value = True
    broker.setup_infrastructure.return_value = None
    broker.send_message.return_value = True
    broker.send_result.return_value = True
    broker.start_consuming.return_value = None
    broker.close.return_value = None
    broker.register_message_handler.return_value = None
    broker.channel = Mock()
    broker.channel.is_open = True
    return broker


@pytest.fixture
def mock_message_handler() -> Mock:
    """Return a mocked message handler."""
    handler = Mock()
    handler.handle_message = Mock()
    handler.set_simulation_handler = Mock()
    return handler


@pytest.fixture
def connect_instance(
    mock_config: Dict[str, Any],
    mock_logger: Mock,
    mock_broker: Mock,
    mock_message_handler: Mock,
) -> Connect:
    """Create a Connect instance with mocked broker/handler factories."""

    def broker_factory(agent_id: str, config: Dict[str, Any]) -> Mock:
        assert agent_id == "test_agent"
        assert config == mock_config
        return mock_broker

    def message_handler_factory(
            agent_id: str, broker: Any, config: Dict[str, Any]) -> Mock:
        assert agent_id == "test_agent"
        assert broker is mock_broker
        assert config == mock_config
        return mock_message_handler

    return Connect(
        agent_id="test_agent",
        config=mock_config,
        broker_type="rabbitmq",
        broker_factory=broker_factory,
        message_handler_factory=message_handler_factory,
        logger=mock_logger,
    )


def test_init_with_unsupported_broker(
        mock_config: Dict[str, Any], mock_logger: Mock) -> None:
    """Unsupported broker types should fail fast."""

    with pytest.raises(ValueError, match="Unsupported broker type: kafka"):
        Connect(
            agent_id="test_agent",
            config=mock_config,
            broker_type="kafka",
            broker_factory=Mock(),
            message_handler_factory=Mock(),
            logger=mock_logger,
        )


def test_connect_success(connect_instance: Connect, mock_broker: Mock) -> None:
    """connect delegates to broker.connect."""
    connect_instance.connect()
    mock_broker.connect.assert_called_once()


def test_setup_success(connect_instance: Connect, mock_broker: Mock) -> None:
    """setup delegates to broker.setup_infrastructure."""
    connect_instance.setup()
    mock_broker.setup_infrastructure.assert_called_once()


def test_register_message_handler_default(
    connect_instance: Connect, mock_broker: Mock, mock_message_handler: Mock
) -> None:
    """Default message handler is registered when no custom callback is provided."""
    connect_instance.register_message_handler()
    mock_broker.register_message_handler.assert_called_once_with(
        mock_message_handler.handle_message
    )


def test_register_message_handler_custom(
        connect_instance: Connect, mock_broker: Mock) -> None:
    """Custom callback should override default message handler."""
    custom_handler = Mock()
    connect_instance.register_message_handler(custom_handler)
    mock_broker.register_message_handler.assert_called_once_with(custom_handler)


def test_register_message_handler_without_broker_raises() -> None:
    """register_message_handler should fail when broker/handler are absent."""
    connect = Connect.__new__(Connect)
    connect.broker = None
    connect.message_handler = None
    with pytest.raises(RuntimeError, match=BROKER_OR_HANDLER_NOT_INITIALIZED_ERROR):
        connect.register_message_handler()


def test_start_consuming_success(
        connect_instance: Connect, mock_broker: Mock) -> None:
    """start_consuming delegates to broker when channel is open."""
    connect_instance.start_consuming()
    mock_broker.start_consuming.assert_called_once()


def test_start_consuming_reconnect_failure(
    connect_instance: Connect, mock_broker: Mock, mock_logger: Mock
) -> None:
    """start_consuming should stop if broker reconnect fails."""
    mock_broker.connect.return_value = False

    connect_instance.start_consuming()

    mock_broker.connect.assert_called_once()
    mock_broker.start_consuming.assert_not_called()
    mock_logger.error.assert_called_once()
    assert mock_logger.error.call_args.args[0] == (
        "Failed to initialize or reopen broker connection. Consumption aborted: %s"
    )
    assert str(mock_logger.error.call_args.args[1]) == BROKER_CONNECTION_FAILED_ERROR


def test_start_consuming_without_broker_raises() -> None:
    """start_consuming must fail when broker is not initialized."""
    connect = Connect.__new__(Connect)
    connect.broker = None
    with pytest.raises(RuntimeError, match=BROKER_NOT_INITIALIZED_ERROR):
        connect.start_consuming()


def test_send_message_success(
        connect_instance: Connect, mock_broker: Mock) -> None:
    """send_message maps destination to routing key and default exchange."""
    result = connect_instance.send_message("target_agent", {"data": "ok"})
    assert result is True
    mock_broker.send_message.assert_called_once_with(
        "ex.sim.result", "test_agent.target_agent", {"data": "ok"}, None
    )


def test_send_message_without_broker_raises() -> None:
    """send_message must fail when broker is not initialized."""
    connect = Connect.__new__(Connect)
    connect.broker = None
    with pytest.raises(RuntimeError, match=BROKER_NOT_INITIALIZED_ERROR):
        connect.send_message("dest", "msg")


def test_send_result_success(connect_instance: Connect,
                             mock_broker: Mock) -> None:
    """send_result delegates to broker.send_result."""
    result = connect_instance.send_result("target_agent", {"result": "ok"})
    assert result is True
    mock_broker.send_result.assert_called_once_with(
        "target_agent", {"result": "ok"})


def test_send_result_without_broker_raises() -> None:
    """send_result must fail when broker is not initialized."""
    connect = Connect.__new__(Connect)
    connect.broker = None
    with pytest.raises(RuntimeError, match=BROKER_NOT_INITIALIZED_ERROR):
        connect.send_result("dest", {"x": 1})


def test_close_without_broker_logs_warning(mock_logger: Mock) -> None:
    """close logs a warning when no broker is initialized."""
    connect = Connect.__new__(Connect)
    connect.broker = None
    connect.logger = mock_logger
    connect.close()
    mock_logger.warning.assert_called_once_with(
        "Attempted to close a non-initialized broker"
    )


def test_set_simulation_handler(
    connect_instance: Connect, mock_message_handler: Mock
) -> None:
    """set_simulation_handler delegates to message handler implementation."""
    handler = Mock()
    connect_instance.set_simulation_handler(handler)
    mock_message_handler.set_simulation_handler.assert_called_once_with(handler)
