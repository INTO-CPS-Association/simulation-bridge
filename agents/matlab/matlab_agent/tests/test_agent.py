from unittest import mock

import pika
import pytest
from src.core.agent import MatlabAgent

# Mocking the necessary components


@pytest.fixture
def mock_config_manager():
    """Provide a mock instance of ConfigManager."""
    with mock.patch("src.core.agent.ConfigManager") as MockConfigManager:
        instance = MockConfigManager.return_value
        instance.get_config.return_value = {
            "rabbitmq": {
                "host": "localhost",
                "port": 5672,
                "username": "guest",
                "password": "guest"
            }
        }
        yield instance


@pytest.fixture
def mock_rabbitmq_manager():
    """Provide a mock instance of RabbitMQManager."""
    with mock.patch("src.core.agent.RabbitMQManager") as MockRabbitMQManager:
        instance = MockRabbitMQManager.return_value
        yield instance


@pytest.fixture
def mock_message_handler():
    """Provide a mock instance of MessageHandler."""
    with mock.patch("src.core.agent.MessageHandler") as MockMessageHandler:
        instance = MockMessageHandler.return_value
        yield instance


@pytest.fixture
def mock_logger():
    """Provide a mock logger."""
    with mock.patch("src.core.agent.logger") as mock_logger:
        yield mock_logger


@pytest.fixture
def matlab_agent(
        mock_config_manager,
        mock_rabbitmq_manager,
        mock_message_handler):
    """Instantiate MatlabAgent with mocked dependencies."""
    agent = MatlabAgent(agent_id="test-agent")
    return agent


def test_agent_initialization(
        matlab_agent,
        mock_config_manager,
        mock_rabbitmq_manager,
        mock_message_handler):
    """Test that the agent initializes correctly."""
    assert matlab_agent.agent_id == "test-agent"
    mock_config_manager.get_config.assert_called_once()
    mock_rabbitmq_manager.register_message_handler.assert_called_once_with(
        mock_message_handler.handle_message
    )


def test_agent_start(matlab_agent, mock_rabbitmq_manager):
    """Test that the agent starts consuming messages."""
    matlab_agent.start()
    mock_rabbitmq_manager.start_consuming.assert_called_once()


def test_agent_stop(matlab_agent, mock_rabbitmq_manager):
    """Test that the agent stops consuming messages and closes the connection."""
    matlab_agent.stop()
    mock_rabbitmq_manager.close.assert_called_once()


def test_agent_start_handles_keyboard_interrupt(
        matlab_agent, mock_rabbitmq_manager, mock_logger):
    """Test that the agent handles manual interruption (Ctrl+C) correctly."""
    mock_rabbitmq_manager.start_consuming.side_effect = KeyboardInterrupt
    matlab_agent.start()
    mock_rabbitmq_manager.close.assert_called_once()
    mock_logger.info.assert_any_call(
        "Stopping MATLAB agent due to keyboard interrupt")


def test_agent_start_handles_connection_error(
        matlab_agent, mock_rabbitmq_manager, mock_logger):
    """Test that the agent handles ConnectionError correctly."""
    error = ConnectionError("Connection failed")
    mock_rabbitmq_manager.start_consuming.side_effect = error
    matlab_agent.start()
    mock_rabbitmq_manager.close.assert_called_once()
    mock_logger.error.assert_any_call(
        "Connection error while consuming messages: %s", error)


def test_agent_start_handles_timeout_error(
        matlab_agent, mock_rabbitmq_manager, mock_logger):
    """Test that the agent handles TimeoutError correctly."""
    error = TimeoutError("Connection timed out")
    mock_rabbitmq_manager.start_consuming.side_effect = error
    matlab_agent.start()
    mock_rabbitmq_manager.close.assert_called_once()
    mock_logger.error.assert_any_call(
        "Timeout error while consuming messages: %s", error)


def test_agent_start_handles_amqp_error(
        matlab_agent,
        mock_rabbitmq_manager,
        mock_logger):
    """Test that the agent handles AMQP errors correctly."""
    error = pika.exceptions.AMQPError("AMQP error")
    mock_rabbitmq_manager.start_consuming.side_effect = error
    matlab_agent.start()
    mock_rabbitmq_manager.close.assert_called_once()
    mock_logger.error.assert_any_call(
        "RabbitMQ error while consuming messages: %s", error)


def test_agent_start_handles_channel_error(
        matlab_agent, mock_rabbitmq_manager, mock_logger):
    """Test that the agent handles Channel errors correctly."""
    error = pika.exceptions.ChannelError("Channel error")
    mock_rabbitmq_manager.start_consuming.side_effect = error
    matlab_agent.start()
    mock_rabbitmq_manager.close.assert_called_once()
    mock_logger.error.assert_any_call(
        "RabbitMQ error while consuming messages: %s", error)


def test_agent_start_handles_connection_closed_by_broker(
        matlab_agent, mock_rabbitmq_manager, mock_logger):
    """Test that the agent handles ConnectionClosedByBroker correctly."""
    error = pika.exceptions.ConnectionClosedByBroker(0, "Connection closed")
    mock_rabbitmq_manager.start_consuming.side_effect = error
    matlab_agent.start()
    mock_rabbitmq_manager.close.assert_called_once()
    mock_logger.error.assert_any_call(
        "RabbitMQ error while consuming messages: %s", error)


def test_agent_start_handles_generic_exception(
        matlab_agent, mock_rabbitmq_manager, mock_logger):
    """Test that the agent handles generic exceptions correctly."""
    error = Exception("Generic error")
    mock_rabbitmq_manager.start_consuming.side_effect = error
    matlab_agent.start()
    mock_rabbitmq_manager.close.assert_called_once()
    mock_logger.error.assert_any_call(
        "Unexpected error while consuming messages: %s", error)
    mock_logger.exception.assert_called_once_with("Stack trace:")


def test_initialization_with_custom_config_path():
    """Test initialization with a custom config path."""
    with mock.patch("src.core.agent.ConfigManager") as MockConfigManager:
        with mock.patch("src.core.agent.RabbitMQManager") as MockRabbitMQManager:
            with mock.patch("src.core.agent.MessageHandler"):
                config_manager_instance = MockConfigManager.return_value
                config_manager_instance.get_config.return_value = {
                    "some": "config"}

                agent = MatlabAgent(
                    agent_id="test-agent",
                    config_path="/custom/path/config.yaml")

                MockConfigManager.assert_called_once_with(
                    "/custom/path/config.yaml")
                MockRabbitMQManager.assert_called_once_with(
                    "test-agent", {"some": "config"})
