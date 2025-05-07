import pytest
from unittest import mock
from src.core.agent import MatlabAgent

# Mocking the necessary components
from src.core.config_manager import ConfigManager
from src.core.rabbitmq_manager import RabbitMQManager
from src.handlers.message_handler import MessageHandler


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
def matlab_agent(mock_config_manager, mock_rabbitmq_manager, mock_message_handler):
    """Instantiate MatlabAgent with mocked dependencies."""
    agent = MatlabAgent(agent_id="test-agent")
    return agent


def test_agent_initialization(matlab_agent, mock_config_manager, mock_rabbitmq_manager, mock_message_handler):
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


def test_agent_start_handles_keyboard_interrupt(matlab_agent, mock_rabbitmq_manager):
    """Test that the agent handles manual interruption (Ctrl+C) correctly."""
    mock_rabbitmq_manager.start_consuming.side_effect = KeyboardInterrupt
    matlab_agent.start()
    mock_rabbitmq_manager.close.assert_called_once()


def test_agent_start_handles_exception(matlab_agent, mock_rabbitmq_manager):
    """Test that the agent handles generic exceptions correctly."""
    mock_rabbitmq_manager.start_consuming.side_effect = Exception("Generic error")
    matlab_agent.start()
    mock_rabbitmq_manager.close.assert_called_once()


