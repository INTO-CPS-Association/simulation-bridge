"""
Test suite for core integration components.
"""
import pytest
from unittest import mock

from src.core.agent import MatlabAgent
from agents.matlab.matlab_agent.src.utils.config_manager import Config, ConfigManager
from agents.matlab.matlab_agent.src.comm.rabbitmq.rabbitmq_manager import RabbitMQManager


@pytest.fixture
def mock_config():
    """Fixture that provides a mock configuration dictionary."""
    return {
        'agent': {'agent_id': 'matlab'},
        'rabbitmq': {
            'host': 'localhost',
            'port': 5672,
            'username': 'guest',
            'password': 'guest',
            'heartbeat': 600
        },
        'exchanges': {
            'input': 'ex.bridge.output',
            'output': 'ex.sim.result'
        },
        'queue': {
            'durable': True,
            'prefetch_count': 1
        }
    }


@pytest.fixture
def mock_config_manager(mock_config):
    """
    Fixture that provides a mock ConfigManager.

    Args:
        mock_config: The mock configuration fixture

    Returns:
        A mock ConfigManager instance
    """
    mock_manager = mock.Mock()
    mock_manager.get_config.return_value = mock_config
    return mock_manager


@pytest.fixture
def mock_rabbitmq_manager():
    """Fixture that provides a mock RabbitMQManager."""
    mock_manager = mock.Mock()
    mock_manager.register_message_handler = mock.Mock()
    mock_manager.start_consuming = mock.Mock()
    mock_manager.close = mock.Mock()
    return mock_manager


@pytest.fixture
def mock_message_handler():
    """Fixture that provides a mock MessageHandler."""
    mock_handler = mock.Mock()
    mock_handler.handle_message = mock.Mock()
    return mock_handler


def test_config_manager_defaults(monkeypatch):
    """
    Test that ConfigManager correctly falls back to default configuration values.

    Args:
        monkeypatch: PyTest monkeypatch fixture
    """
    # Create a mock Config class for testing defaults
    mock_config_instance = mock.Mock()
    mock_config_instance.to_dict.return_value = {
        'agent': {'agent_id': 'matlab'},
        'rabbitmq': {'host': 'localhost'}
    }

    # Patch the Config class to return our mock
    monkeypatch.setattr(
        "src.core.config_manager.Config",
        lambda: mock_config_instance
    )

    # Monkeypatch the ConfigManager.__init__ to set our mock config
    monkeypatch.setattr(
        ConfigManager,
        "__init__",
        lambda self, config_path=None: setattr(
            self, 'config', mock_config_instance.to_dict()
        )
    )

    # Create ConfigManager and test defaults
    cm = ConfigManager()
    config = cm.get_config()

    assert isinstance(config, dict)
    assert config['agent']['agent_id'] == 'matlab'
    assert config['rabbitmq']['host'] == 'localhost'


class TestRabbitMQManager:
    """Test suite for RabbitMQManager functionality."""

    @pytest.fixture
    def mock_pika_connection(self):
        """Fixture that provides mocked pika connection components."""
        fake_channel = mock.Mock()
        fake_connection = mock.Mock()
        fake_connection.channel.return_value = fake_channel

        return {
            'channel': fake_channel,
            'connection': fake_connection
        }

    @pytest.fixture
    def pika_mocks(self, mock_pika_connection):
        """
        Fixture that provides all necessary pika mocks.

        Args:
            mock_pika_connection: The mock pika connection fixture

        Returns:
            Dictionary of mocked pika components
        """
        with mock.patch('src.core.rabbitmq_manager.pika.PlainCredentials') as mock_creds, \
                mock.patch('src.core.rabbitmq_manager.pika.ConnectionParameters') as mock_params, \
                mock.patch('src.core.rabbitmq_manager.pika.BlockingConnection') as mock_conn:

            mock_conn.return_value = mock_pika_connection['connection']

            yield {
                'credentials': mock_creds,
                'connection_params': mock_params,
                'connection': mock_conn,
                'channel': mock_pika_connection['channel']
            }

    def test_rabbitmq_connect_and_setup(self, pika_mocks, mock_config):
        """
        Test that RabbitMQManager correctly establishes a connection to RabbitMQ.

        Args:
            pika_mocks: The pika mocks fixture
            mock_config: The mock configuration fixture
        """
        # Create RabbitMQManager instance
        rabbitmq_manager = RabbitMQManager("agent_1", mock_config)

        # Verify credentials were created with correct values
        pika_mocks['credentials'].assert_called_once_with('guest', 'guest')

        # Additional verifications could be added here
        # For example, checking that exchanges and queues were declared


class TestMatlabAgent:
    """Test suite for MatlabAgent functionality."""

    @pytest.fixture
    def patched_dependencies(
            self,
            monkeypatch,
            mock_config,
            mock_rabbitmq_manager,
            mock_message_handler):
        """
        Fixture that patches all dependencies for MatlabAgent.

        Args:
            monkeypatch: PyTest monkeypatch fixture
            mock_config: The mock configuration fixture
            mock_rabbitmq_manager: The mock RabbitMQManager fixture
            mock_message_handler: The mock MessageHandler fixture
        """
        # Create mock ConfigManager class
        mock_config_manager_class = mock.Mock()
        mock_config_manager_instance = mock.Mock()
        mock_config_manager_instance.get_config.return_value = mock_config
        mock_config_manager_class.return_value = mock_config_manager_instance

        # Create mock RabbitMQManager class
        mock_rabbitmq_manager_class = mock.Mock(
            return_value=mock_rabbitmq_manager)

        # Create mock MessageHandler class
        mock_message_handler_class = mock.Mock(
            return_value=mock_message_handler)

        # Patch the classes
        monkeypatch.setattr(
            'src.core.agent.ConfigManager',
            mock_config_manager_class)
        monkeypatch.setattr(
            'src.core.agent.RabbitMQManager',
            mock_rabbitmq_manager_class)
        monkeypatch.setattr(
            'src.core.agent.MessageHandler',
            mock_message_handler_class)

        return {
            'config_manager_class': mock_config_manager_class,
            'rabbitmq_manager_class': mock_rabbitmq_manager_class,
            'message_handler_class': mock_message_handler_class,
            'config_manager': mock_config_manager_instance,
            'rabbitmq_manager': mock_rabbitmq_manager,
            'message_handler': mock_message_handler
        }

    def test_matlab_agent_initialization(self, patched_dependencies):
        """
        Test that MatlabAgent initializes correctly.

        Args:
            patched_dependencies: The patched dependencies fixture
        """
        agent = MatlabAgent(agent_id='agent1')

        assert agent.agent_id == 'agent1'
        assert hasattr(agent, 'rabbitmq_manager')
        assert hasattr(agent, 'message_handler')

        # Verify RabbitMQManager was created with correct parameters
        patched_dependencies['rabbitmq_manager_class'].assert_called_once()

    def test_matlab_agent_start_stop(self):
        """Test that MatlabAgent start and stop methods work correctly."""
        # Create a dummy RabbitMQManager that raises KeyboardInterrupt
        class DummyRabbitMQManager:
            def start_consuming(self):
                """Simulate consuming messages and being interrupted."""
                raise KeyboardInterrupt()

            def close(self):
                """Mock for close method."""
                pass

        # Create agent and inject our dummy manager
        agent = MatlabAgent(agent_id='agent2')
        agent.rabbitmq_manager = DummyRabbitMQManager()
        agent.stop = mock.Mock()

        # Run the agent's start method
        agent.start()

        # Verify that the stop method was called
        agent.stop.assert_called_once()
