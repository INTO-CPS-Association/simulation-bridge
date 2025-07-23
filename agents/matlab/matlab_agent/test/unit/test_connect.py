"""
Test module for the Connect communication wrapper.

This suite exercises all public methods of Connect with both unit-level
isolation (using mocks) and an integration-style workflow test.  Error paths,
edge cases and successful flows are all covered.
"""

# pylint: disable=missing-function-docstring, too-many-positional-arguments

from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

from src.comm.connect import Connect


class TestConnect:
    """Unit-level tests for the :class:`Connect` communication wrapper."""

    @pytest.fixture
    def mock_config(self, dummy_credentials) -> Dict[str, Any]:
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
    def agent_id(self) -> str:
        """Provide a test-friendly agent identifier."""
        return "test_agent_001"

    @pytest.fixture
    def mock_rabbitmq_manager(self) -> Mock:
        """Return a fully-mocked RabbitMQ manager."""
        mgr = Mock()
        mgr.connect.return_value = True
        mgr.setup_infrastructure.return_value = None
        mgr.send_message.return_value = True
        mgr.send_result.return_value = True
        mgr.start_consuming.return_value = None
        mgr.close.return_value = None
        mgr.register_message_handler.return_value = None
        mgr.channel = Mock()
        mgr.channel.is_open = True
        return mgr

    @pytest.fixture
    def mock_message_handler(self) -> Mock:
        """Return a mocked message handler."""
        handler = Mock()
        handler.handle_message = Mock()
        handler.set_simulation_handler = Mock()
        return handler

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_init_with_rabbitmq(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        # Arrange
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Act
        connect = Connect(agent_id, mock_config, "rabbitmq")

        # Assert
        assert connect.agent_id == agent_id
        assert connect.config == mock_config
        assert connect.broker_type == "rabbitmq"
        assert connect.broker is mock_rabbitmq_manager
        assert connect.message_handler is mock_message_handler

        mock_rabbitmq_manager_class.assert_called_once_with(
            agent_id, mock_config)
        mock_message_handler_class.assert_called_once_with(
            agent_id, mock_rabbitmq_manager, mock_config
        )

    def test_init_with_unsupported_broker(
            self, agent_id: str, mock_config: Dict[str, Any]) -> None:
        with pytest.raises(ValueError, match="Unsupported broker type: kafka"):
            Connect(agent_id, mock_config, "kafka")

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_connect_success(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        connect = Connect(agent_id, mock_config)
        connect.connect()

        mock_rabbitmq_manager.connect.assert_called_once()

    def test_connect_without_broker(self) -> None:
        connect = Connect.__new__(Connect)
        connect.broker = None
        with pytest.raises(RuntimeError, match="Broker not initialized"):
            connect.connect()

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_setup_success(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        connect = Connect(agent_id, mock_config)
        connect.setup()

        mock_rabbitmq_manager.setup_infrastructure.assert_called_once()

    def test_setup_without_broker(self) -> None:
        connect = Connect.__new__(Connect)
        connect.broker = None
        with pytest.raises(RuntimeError, match="Broker not initialized"):
            connect.setup()

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_register_message_handler_default(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        connect = Connect(agent_id, mock_config)
        connect.register_message_handler()

        mock_rabbitmq_manager.register_message_handler.assert_called_once_with(
            mock_message_handler.handle_message
        )

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_register_message_handler_custom(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        custom_handler = Mock()
        connect = Connect(agent_id, mock_config)
        connect.register_message_handler(custom_handler)

        mock_rabbitmq_manager.register_message_handler.assert_called_once_with(
            custom_handler)

    def test_register_message_handler_without_broker(self) -> None:
        connect = Connect.__new__(Connect)
        connect.broker = None
        connect.message_handler = None
        with pytest.raises(RuntimeError, match="Broker or message handler not initialized"):
            connect.register_message_handler()

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_start_consuming_success(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        connect = Connect(agent_id, mock_config)
        connect.start_consuming()

        mock_rabbitmq_manager.start_consuming.assert_called_once()

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    @patch("src.comm.connect.logger")
    def test_start_consuming_with_reconnection(
        self,
        mock_logger: Mock,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler
        mock_rabbitmq_manager.channel = None  # channel closed
        mock_rabbitmq_manager.connect.return_value = True

        connect = Connect(agent_id, mock_config)
        connect.start_consuming()

        mock_rabbitmq_manager.connect.assert_called_once()
        mock_rabbitmq_manager.start_consuming.assert_called_once()
        mock_logger.debug.assert_called()

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    @patch("src.comm.connect.logger")
    def test_start_consuming_failed_reconnection(
        self,
        mock_logger: Mock,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler
        mock_rabbitmq_manager.channel = None
        mock_rabbitmq_manager.connect.return_value = False

        connect = Connect(agent_id, mock_config)
        connect.start_consuming()

        mock_logger.error.assert_called_with(
            "Failed to initialize or reopen channel. Consumption aborted."
        )
        mock_rabbitmq_manager.start_consuming.assert_not_called()

    def test_start_consuming_without_broker(self) -> None:
        connect = Connect.__new__(Connect)
        connect.broker = None
        with pytest.raises(RuntimeError, match="Broker not initialized"):
            connect.start_consuming()

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_send_message_success(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        connect = Connect(agent_id, mock_config)
        result = connect.send_message("target_agent", {"data": "test"})

        assert result is True
        mock_rabbitmq_manager.send_message.assert_called_once_with(
            "ex.sim.result", f"{agent_id}.target_agent", {"data": "test"}, None
        )

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_send_message_with_kwargs(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        connect = Connect(agent_id, mock_config)
        result = connect.send_message(
            "target_agent",
            {"data": "test"},
            exchange="custom.exchange",
            routing_key="custom.key",
            properties={"priority": 5},
        )

        assert result is True
        mock_rabbitmq_manager.send_message.assert_called_once_with(
            "custom.exchange", "custom.key", {"data": "test"}, {"priority": 5}
        )

    def test_send_message_without_broker(self) -> None:
        connect = Connect.__new__(Connect)
        connect.broker = None
        with pytest.raises(RuntimeError, match="Broker not initialized"):
            connect.send_message("dest", "msg")

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_send_result_success(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        connect = Connect(agent_id, mock_config)
        result = connect.send_result("target_agent", {"result": "ok"})

        assert result is True
        mock_rabbitmq_manager.send_result.assert_called_once_with(
            "target_agent", {"result": "ok"}
        )

    def test_send_result_without_broker(self) -> None:
        connect = Connect.__new__(Connect)
        connect.broker = None
        with pytest.raises(RuntimeError, match="Broker not initialized"):
            connect.send_result("dest", "data")

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_close_success(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        connect = Connect(agent_id, mock_config)
        connect.close()

        mock_rabbitmq_manager.close.assert_called_once()

    @patch("src.comm.connect.logger")
    def test_close_without_broker(self, mock_logger: Mock) -> None:
        connect = Connect.__new__(Connect)
        connect.broker = None
        connect.close()
        mock_logger.warning.assert_called_once_with(
            "Attempted to close a non-initialized broker")

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_get_message_handler(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        connect = Connect(agent_id, mock_config)
        assert connect.get_message_handler() is mock_message_handler

    def test_get_message_handler_when_none(self) -> None:
        connect = Connect.__new__(Connect)
        connect.message_handler = None
        assert connect.get_message_handler() is None

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_set_simulation_handler(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        connect = Connect(agent_id, mock_config)
        sim_handler = Mock()
        connect.set_simulation_handler(sim_handler)

        mock_message_handler.set_simulation_handler.assert_called_once_with(
            sim_handler)

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_set_simulation_handler_without_message_handler(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
    ) -> None:
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = None

        connect = Connect.__new__(Connect)
        connect.message_handler = None
        connect.set_simulation_handler(Mock())  # should not raise


class TestConnectIntegration:
    """Light-weight integration test covering a typical end-to-end workflow."""

    @patch("src.comm.connect.RabbitMQManager")
    @patch("src.comm.connect.MessageHandler")
    def test_full_workflow(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
    ) -> None:
        # Arrange
        mock_mgr = Mock()
        mock_mgr.connect.return_value = True
        mock_mgr.setup_infrastructure.return_value = None
        mock_mgr.send_message.return_value = True
        mock_mgr.channel = Mock(is_open=True)

        mock_handler = Mock()

        mock_rabbitmq_manager_class.return_value = mock_mgr
        mock_message_handler_class.return_value = mock_handler

        agent_id = "integration_test_agent"
        config = {
            "exchanges": {"output": "ex.test.output"},
            "rabbitmq": {"host": "localhost"},
        }

        # Act
        connect = Connect(agent_id, config)
        connect.connect()
        connect.setup()
        connect.register_message_handler()
        connect.start_consuming()
        assert connect.send_message("target", {"test": "data"}) is True
        connect.close()

        # Assert
        mock_mgr.connect.assert_called_once()
        mock_mgr.setup_infrastructure.assert_called_once()
        mock_mgr.register_message_handler.assert_called_once()
        mock_mgr.start_consuming.assert_called_once()
        mock_mgr.send_message.assert_called_once()
        mock_mgr.close.assert_called_once()
