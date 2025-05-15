"""Unit tests for the MatlabAgent class with improved structure and best practices."""

import pytest
from unittest import mock

import pika
from src.core.agent import MatlabAgent


@pytest.fixture
def config_dict():
    """Return a standard configuration dictionary for testing."""
    return {
        "rabbitmq": {
            "host": "localhost",
            "port": 5672,
            "username": "guest",
            "password": "guest"
        }
    }


@pytest.fixture
def mock_config_manager(config_dict):
    """Provide a mock instance of ConfigManager with standard configuration."""
    with mock.patch("src.core.agent.ConfigManager") as mock_cm:
        instance = mock_cm.return_value
        instance.get_config.return_value = config_dict
        yield instance


@pytest.fixture
def mock_rabbitmq_manager():
    """Provide a mock instance of RabbitMQManager."""
    with mock.patch("src.core.agent.RabbitMQManager") as mock_rmq:
        instance = mock_rmq.return_value
        yield instance


@pytest.fixture
def mock_message_handler():
    """Provide a mock instance of MessageHandler."""
    with mock.patch("src.core.agent.MessageHandler") as mock_mh:
        instance = mock_mh.return_value
        yield instance


@pytest.fixture
def mock_logger():
    """Provide a mock logger."""
    with mock.patch("src.core.agent.logger") as mock_log:
        yield mock_log


@pytest.fixture
def matlab_agent(
        mock_config_manager,
        mock_rabbitmq_manager,
        mock_message_handler):
    """Create a MatlabAgent instance with mocked dependencies."""
    return MatlabAgent(agent_id="test-agent")


class TestMatlabAgentInitialization:
    """Tests for MatlabAgent initialization."""

    def test_initialization_with_default_parameters(
            self, matlab_agent, mock_config_manager, mock_rabbitmq_manager,
            mock_message_handler):
        """Test that the agent initializes correctly with default parameters."""
        assert matlab_agent.agent_id == "test-agent"
        mock_config_manager.get_config.assert_called_once()
        mock_rabbitmq_manager.register_message_handler.assert_called_once_with(
            mock_message_handler.handle_message
        )

    def test_initialization_with_custom_config_path(self):
        """Test initialization with a custom config path."""
        with mock.patch("src.core.agent.ConfigManager") as mock_cm:
            with mock.patch("src.core.agent.RabbitMQManager") as mock_rmq:
                with mock.patch("src.core.agent.MessageHandler"):
                    mock_cm_instance = mock_cm.return_value
                    mock_cm_instance.get_config.return_value = {
                        "some": "config"}

                    agent = MatlabAgent(
                        agent_id="test-agent",
                        config_path="/custom/path/config.yaml"
                    )

                    mock_cm.assert_called_once_with("/custom/path/config.yaml")
                    mock_rmq.assert_called_once_with(
                        "test-agent", {"some": "config"})


class TestMatlabAgentOperations:
    """Tests for MatlabAgent operations like start and stop."""

    def test_start(self, matlab_agent, mock_rabbitmq_manager):
        """Test that the agent starts consuming messages."""
        matlab_agent.start()
        mock_rabbitmq_manager.start_consuming.assert_called_once()

    def test_stop(self, matlab_agent, mock_rabbitmq_manager):
        """Test that the agent stops consuming messages and closes the connection."""
        matlab_agent.stop()
        mock_rabbitmq_manager.close.assert_called_once()


class TestMatlabAgentErrorHandling:
    """Tests for error handling in MatlabAgent."""

    @pytest.mark.parametrize(
        "exception,log_method,expected_message", [
            (KeyboardInterrupt(), "info", "Stopping MATLAB agent due to keyboard interrupt"),
            (ConnectionError("Connection failed"), "error",
             "Connection error while consuming messages: %s"),
            (TimeoutError("Connection timed out"), "error",
             "Timeout error while consuming messages: %s"),
            (pika.exceptions.AMQPError("AMQP error"), "error",
             "RabbitMQ error while consuming messages: %s"),
            (pika.exceptions.ChannelError("Channel error"), "error",
             "RabbitMQ error while consuming messages: %s"),
            (pika.exceptions.ConnectionClosedByBroker(0, "Connection closed"), "error",
             "RabbitMQ error while consuming messages: %s"),
            (Exception("Generic error"), "error",
             "Unexpected error while consuming messages: %s"),
        ]
    )
    def test_error_handling(
            self,
            matlab_agent,
            mock_rabbitmq_manager,
            mock_logger,
            exception,
            log_method,
            expected_message):
        mock_rabbitmq_manager.start_consuming.side_effect = exception
        matlab_agent.start()
        mock_rabbitmq_manager.close.assert_called_once()

        if "%s" in expected_message:
            # Aspettiamo chiamata con placeholder e l'eccezione come secondo
            # argomento
            getattr(
                mock_logger,
                log_method).assert_any_call(
                expected_message,
                exception)
        else:
            # Nessun placeholder, messaggio intero
            getattr(mock_logger, log_method).assert_any_call(expected_message)
