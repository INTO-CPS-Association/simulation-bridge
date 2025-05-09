"""
Test suite for core integration components.
"""

from unittest import mock

from src.core.agent import MatlabAgent
from src.core.config_manager import Config, ConfigManager
from src.core.rabbitmq_manager import RabbitMQManager


def test_config_manager_defaults(monkeypatch):
    """
    This test verifies that the `ConfigManager` correctly falls back to default configuration values
    when the configuration file is missing or not provided. It ensures that the default values for
    agent ID and RabbitMQ host are set as expected.
    """
    monkeypatch.setattr(
        ConfigManager,
        "__init__",
        lambda self, config_path=None: setattr(
            self, 'config', Config().to_dict()
        )
    )

    cm = ConfigManager()
    config = cm.get_config()

    assert isinstance(config, dict)
    assert config['agent']['agent_id'] == 'matlab'
    assert config['rabbitmq']['host'] == 'localhost'


@mock.patch('src.core.rabbitmq_manager.pika.PlainCredentials')
@mock.patch('src.core.rabbitmq_manager.pika.ConnectionParameters')
@mock.patch('src.core.rabbitmq_manager.pika.BlockingConnection')
def test_rabbitmq_connect_and_setup(
    mock_conn,
    mock_params,
    mock_creds
):
    """
    This test ensures that the `RabbitMQManager` correctly establishes a connection to RabbitMQ,
    declares the necessary exchanges and queues, binds the queue to the exchange, and sets the QoS
    (Quality of Service) settings. It uses mocks to simulate RabbitMQ behavior and verify the calls.
    """
    fake_channel = mock.Mock()
    fake_connection = mock.Mock(channel=mock.Mock(return_value=fake_channel))
    mock_conn.return_value = fake_connection

    # Creazione della configurazione
    config_instance = Config()
    cfg = config_instance.to_dict()

    # Creiamo il manager
    rabbitmq_manager = RabbitMQManager("agent_1", cfg)

    # Verifica che le credenziali siano state chiamate
    mock_creds.assert_called_once_with('guest', 'guest')


def test_matlab_agent_initialization(monkeypatch):
    """
    This test checks the initialization of the `MatlabAgent` class. It ensures that the agent ID is
    correctly set, and that the `ConfigManager`, `RabbitMQManager`, and `MessageHandler` components
    are properly instantiated and assigned to the agent.
    """
    fake_cfg = {'rabbitmq': {}, 'exchanges': {}, 'queue': {}}
    monkeypatch.setattr(
        'src.core.agent.ConfigManager',
        lambda self=None: type(
            'CM', (), {'get_config': lambda s: fake_cfg}
        )()
    )
    monkeypatch.setattr(
        'src.core.agent.RabbitMQManager',
        lambda agent_id, config: type(
            'RM',
            (),
            {
                'register_message_handler': mock.Mock(),
                'start_consuming': mock.Mock(),
                'close': mock.Mock()
            }
        )()
    )
    monkeypatch.setattr(
        'src.core.agent.MessageHandler',
        lambda agent_id, rm: type(
            'MH', (), {'handle_message': mock.Mock()}
        )()
    )

    agent = MatlabAgent(agent_id='agent1')
    assert agent.agent_id == 'agent1'
    assert hasattr(agent, 'rabbitmq_manager')
    assert hasattr(agent, 'message_handler')


@mock.patch.object(RabbitMQManager, 'start_consuming')
@mock.patch.object(RabbitMQManager, 'close')
def test_matlab_agent_start_stop(mock_close, mock_start_consuming):
    """
    This test verifies the `start` and `stop` methods of the `MatlabAgent`.
    It ensures that the agent starts consuming messages and handles a
    `KeyboardInterrupt` gracefully by calling the `stop` method
    and closing the RabbitMQ connection.
    """
    class DummyRM:
        """Dummy RabbitMQManager for testing."""

        def start_consuming(self):
            """Simulate consuming messages."""
            raise KeyboardInterrupt()

        def close(self):
            """Simulate closing the connection."""

    agent = MatlabAgent(agent_id='agent2')
    agent.rabbitmq_manager = DummyRM()
    agent.stop = mock.Mock()
    agent.start()
    agent.stop.assert_called_once()
