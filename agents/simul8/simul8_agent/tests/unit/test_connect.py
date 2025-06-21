"""
Test module for the Connect communication wrapper.

This module contains comprehensive tests for the Connect class,
testing all its methods and error conditions.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional, Callable

# Import the class under test
# Assuming the structure: from communication.connect import Connect
# Adjust the import path according to your project structure
from src.comm.connect import Connect


class TestConnect:
    """Test class for the Connect communication wrapper."""

    @pytest.fixture
    def mock_config(self) -> Dict[str, Any]:
        """Provide a mock configuration for testing."""
        return {
            "exchanges": {
                "output": "ex.sim.result",
                "input": "ex.sim.input"
            },
            "rabbitmq": {
                "host": "localhost",
                "port": 5672,
                "username": "guest",
                "password": "guest"
            }
        }

    @pytest.fixture
    def agent_id(self) -> str:
        """Provide a test agent ID."""
        return "test_agent_001"

    @pytest.fixture
    def mock_rabbitmq_manager(self) -> Mock:
        """Create a mock RabbitMQ manager."""
        mock_manager = Mock()
        mock_manager.connect.return_value = True
        mock_manager.setup_infrastructure.return_value = None
        mock_manager.send_message.return_value = True
        mock_manager.send_result.return_value = True
        mock_manager.start_consuming.return_value = None
        mock_manager.close.return_value = None
        mock_manager.register_message_handler.return_value = None
        mock_manager.channel = Mock()
        mock_manager.channel.is_open = True
        return mock_manager

    @pytest.fixture
    def mock_message_handler(self) -> Mock:
        """Create a mock message handler."""
        mock_handler = Mock()
        mock_handler.handle_message = Mock()
        mock_handler.set_simulation_handler = Mock()
        return mock_handler

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_init_with_rabbitmq(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test initialization with RabbitMQ broker type."""
        # Setup mocks
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Create Connect instance
        connect = Connect(agent_id, mock_config, "rabbitmq")

        # Assertions
        assert connect.agent_id == agent_id
        assert connect.config == mock_config
        assert connect.broker_type == "rabbitmq"
        assert connect.broker == mock_rabbitmq_manager
        assert connect.message_handler == mock_message_handler

        # Verify initialization calls
        mock_rabbitmq_manager_class.assert_called_once_with(
            agent_id, mock_config)
        mock_message_handler_class.assert_called_once_with(
            agent_id, mock_rabbitmq_manager, mock_config
        )

    def test_init_with_unsupported_broker(
        self,
        agent_id: str,
        mock_config: Dict[str, Any]
    ) -> None:
        """Test initialization with unsupported broker type."""
        with pytest.raises(ValueError, match="Unsupported broker type: kafka"):
            Connect(agent_id, mock_config, "kafka")

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_connect_success(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test successful connection to broker."""
        # Setup mocks
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Create Connect instance and connect
        connect = Connect(agent_id, mock_config)
        connect.connect()

        # Verify connect was called
        mock_rabbitmq_manager.connect.assert_called_once()

    def test_connect_without_broker(self) -> None:
        """Test connect method when broker is not initialized."""
        # Create instance without proper initialization
        connect = Connect.__new__(Connect)
        connect.broker = None

        with pytest.raises(RuntimeError, match="Broker not initialized"):
            connect.connect()

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_setup_success(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test successful setup of infrastructure."""
        # Setup mocks
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Create Connect instance and setup
        connect = Connect(agent_id, mock_config)
        connect.setup()

        # Verify setup was called
        mock_rabbitmq_manager.setup_infrastructure.assert_called_once()

    def test_setup_without_broker(self) -> None:
        """Test setup method when broker is not initialized."""
        # Create instance without proper initialization
        connect = Connect.__new__(Connect)
        connect.broker = None

        with pytest.raises(RuntimeError, match="Broker not initialized"):
            connect.setup()

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_register_message_handler_default(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test registering default message handler."""
        # Setup mocks
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Create Connect instance and register handler
        connect = Connect(agent_id, mock_config)
        connect.register_message_handler()

        # Verify handler registration
        mock_rabbitmq_manager.register_message_handler.assert_called_once_with(
            mock_message_handler.handle_message
        )

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_register_message_handler_custom(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test registering custom message handler."""
        # Setup mocks
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Create custom handler
        custom_handler = Mock()

        # Create Connect instance and register custom handler
        connect = Connect(agent_id, mock_config)
        connect.register_message_handler(custom_handler)

        # Verify custom handler registration
        mock_rabbitmq_manager.register_message_handler.assert_called_once_with(
            custom_handler
        )

    def test_register_message_handler_without_broker(self) -> None:
        """Test registering message handler when broker is not initialized."""
        # Create instance without proper initialization
        connect = Connect.__new__(Connect)
        connect.broker = None
        connect.message_handler = None

        with pytest.raises(
            RuntimeError,
            match="Broker or message handler not initialized"
        ):
            connect.register_message_handler()

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_start_consuming_success(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test successful start of message consumption."""
        # Setup mocks
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Create Connect instance and start consuming
        connect = Connect(agent_id, mock_config)
        connect.start_consuming()

        # Verify start_consuming was called
        mock_rabbitmq_manager.start_consuming.assert_called_once()

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    @patch('src.comm.connect.logger')
    def test_start_consuming_with_reconnection(
        self,
        mock_logger: Mock,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test start consuming with channel reconnection."""
        # Setup mocks - channel is closed initially
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler
        mock_rabbitmq_manager.channel = None
        mock_rabbitmq_manager.connect.return_value = True

        # Create Connect instance and start consuming
        connect = Connect(agent_id, mock_config)
        connect.start_consuming()

        # Verify reconnection attempt and successful consumption
        mock_rabbitmq_manager.connect.assert_called_once()
        mock_rabbitmq_manager.start_consuming.assert_called_once()
        mock_logger.debug.assert_called()

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    @patch('src.comm.connect.logger')
    def test_start_consuming_failed_reconnection(
        self,
        mock_logger: Mock,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test start consuming with failed reconnection."""
        # Setup mocks - channel is closed and reconnection fails
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler
        mock_rabbitmq_manager.channel = None
        mock_rabbitmq_manager.connect.return_value = False

        # Create Connect instance and start consuming
        connect = Connect(agent_id, mock_config)
        connect.start_consuming()

        # Verify error logging and no consumption attempt
        mock_logger.error.assert_called_with(
            "Failed to initialize or reopen channel. Consumption aborted."
        )
        mock_rabbitmq_manager.start_consuming.assert_not_called()

    def test_start_consuming_without_broker(self) -> None:
        """Test start consuming when broker is not initialized."""
        # Create instance without proper initialization
        connect = Connect.__new__(Connect)
        connect.broker = None

        with pytest.raises(RuntimeError, match="Broker not initialized"):
            connect.start_consuming()

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_send_message_success(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test successful message sending."""
        # Setup mocks
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Create Connect instance
        connect = Connect(agent_id, mock_config)

        # Send message
        destination = "target_agent"
        message = {"data": "test_message"}
        result = connect.send_message(destination, message)

        # Verify message was sent
        assert result is True
        expected_exchange = "ex.sim.result"
        expected_routing_key = f"{agent_id}.{destination}"
        mock_rabbitmq_manager.send_message.assert_called_once_with(
            expected_exchange, expected_routing_key, message, None
        )

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_send_message_with_kwargs(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test message sending with custom parameters."""
        # Setup mocks
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Create Connect instance
        connect = Connect(agent_id, mock_config)

        # Send message with custom parameters
        destination = "target_agent"
        message = {"data": "test_message"}
        custom_exchange = "custom.exchange"
        custom_routing_key = "custom.routing.key"
        properties = {"priority": 5}

        result = connect.send_message(
            destination,
            message,
            exchange=custom_exchange,
            routing_key=custom_routing_key,
            properties=properties
        )

        # Verify message was sent with custom parameters
        assert result is True
        mock_rabbitmq_manager.send_message.assert_called_once_with(
            custom_exchange, custom_routing_key, message, properties
        )

    def test_send_message_without_broker(self) -> None:
        """Test send message when broker is not initialized."""
        # Create instance without proper initialization
        connect = Connect.__new__(Connect)
        connect.broker = None

        with pytest.raises(RuntimeError, match="Broker not initialized"):
            connect.send_message("destination", "message")

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_send_result_success(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test successful result sending."""
        # Setup mocks
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Create Connect instance
        connect = Connect(agent_id, mock_config)

        # Send result
        destination = "target_agent"
        result_data = {"status": "success", "data": {"value": 42}}
        result = connect.send_result(destination, result_data)

        # Verify result was sent
        assert result is True
        mock_rabbitmq_manager.send_result.assert_called_once_with(
            destination, result_data
        )

    def test_send_result_without_broker(self) -> None:
        """Test send result when broker is not initialized."""
        # Create instance without proper initialization
        connect = Connect.__new__(Connect)
        connect.broker = None

        with pytest.raises(RuntimeError, match="Broker not initialized"):
            connect.send_result("destination", {"result": "data"})

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_close_success(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test successful connection closing."""
        # Setup mocks
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Create Connect instance and close
        connect = Connect(agent_id, mock_config)
        connect.close()

        # Verify close was called
        mock_rabbitmq_manager.close.assert_called_once()

    @patch('src.comm.connect.logger')
    def test_close_without_broker(self, mock_logger: Mock) -> None:
        """Test closing when broker is not initialized."""
        # Create instance without proper initialization
        connect = Connect.__new__(Connect)
        connect.broker = None

        # Close connection
        connect.close()

        # Verify warning was logged
        mock_logger.warning.assert_called_once_with(
            "Attempted to close a non-initialized broker"
        )

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_get_message_handler(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test getting the message handler."""
        # Setup mocks
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Create Connect instance
        connect = Connect(agent_id, mock_config)

        # Get message handler
        handler = connect.get_message_handler()

        # Verify handler is returned
        assert handler == mock_message_handler

    def test_get_message_handler_when_none(self) -> None:
        """Test getting message handler when it's None."""
        # Create instance without proper initialization
        connect = Connect.__new__(Connect)
        connect.message_handler = None

        # Get message handler
        handler = connect.get_message_handler()

        # Verify None is returned
        assert handler is None

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_set_simulation_handler(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock,
        mock_message_handler: Mock
    ) -> None:
        """Test setting simulation handler."""
        # Setup mocks
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Create Connect instance
        connect = Connect(agent_id, mock_config)

        # Create simulation handler
        simulation_handler = Mock()

        # Set simulation handler
        connect.set_simulation_handler(simulation_handler)

        # Verify handler was set
        mock_message_handler.set_simulation_handler.assert_called_once_with(
            simulation_handler
        )

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_set_simulation_handler_without_message_handler(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock,
        agent_id: str,
        mock_config: Dict[str, Any],
        mock_rabbitmq_manager: Mock
    ) -> None:
        """Test setting simulation handler when message handler is None."""
        # Setup mocks
        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = None

        # Create Connect instance (this will make message_handler None)
        connect = Connect.__new__(Connect)
        connect.message_handler = None

        # Create simulation handler
        simulation_handler = Mock()

        # Set simulation handler (should not raise exception)
        connect.set_simulation_handler(simulation_handler)

        # No assertion needed - just verify no exception is raised


class TestConnectIntegration:
    """Integration tests for Connect class workflow."""

    @patch('src.comm.connect.RabbitMQManager')
    @patch('src.comm.connect.MessageHandler')
    def test_full_workflow(
        self,
        mock_message_handler_class: Mock,
        mock_rabbitmq_manager_class: Mock
    ) -> None:
        """Test a complete workflow from initialization to cleanup."""
        # Setup mocks
        mock_rabbitmq_manager = Mock()
        mock_rabbitmq_manager.connect.return_value = True
        mock_rabbitmq_manager.setup_infrastructure.return_value = None
        mock_rabbitmq_manager.send_message.return_value = True
        mock_rabbitmq_manager.channel = Mock()
        mock_rabbitmq_manager.channel.is_open = True

        mock_message_handler = Mock()

        mock_rabbitmq_manager_class.return_value = mock_rabbitmq_manager
        mock_message_handler_class.return_value = mock_message_handler

        # Configuration and agent ID
        agent_id = "integration_test_agent"
        config = {
            "exchanges": {"output": "ex.test.output"},
            "rabbitmq": {"host": "localhost"}
        }

        # Initialize Connect
        connect = Connect(agent_id, config)

        # Full workflow
        connect.connect()
        connect.setup()
        connect.register_message_handler()
        connect.start_consuming()

        # Send a message
        result = connect.send_message("target", {"test": "data"})
        assert result is True

        # Cleanup
        connect.close()

        # Verify all operations were called
        mock_rabbitmq_manager.connect.assert_called_once()
        mock_rabbitmq_manager.setup_infrastructure.assert_called_once()
        mock_rabbitmq_manager.register_message_handler.assert_called_once()
        mock_rabbitmq_manager.start_consuming.assert_called_once()
        mock_rabbitmq_manager.send_message.assert_called_once()
        mock_rabbitmq_manager.close.assert_called_once()
