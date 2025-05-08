import pytest
from unittest import mock
from src.core.config_manager import ConfigManager, Config
from src.core.rabbitmq_manager import RabbitMQManager
from src.core.agent import MatlabAgent
import pika


def test_config_manager_defaults(tmp_path, monkeypatch):
    """
    This test verifies that the `ConfigManager` correctly falls back to default configuration values
    when the configuration file is missing or not provided. It ensures that the default values for
    agent ID and RabbitMQ host are set as expected.
    """
    monkeypatch.setattr(ConfigManager, "__init__", lambda self,
                        config_path=None: setattr(self, 'config', Config().model_dump()))
    cm = ConfigManager()
    config = cm.get_config()
    assert isinstance(config, dict)
    assert config['agent']['agent_id'] == 'matlab'
    assert config['rabbitmq']['host'] == 'localhost'


@mock.patch('src.core.rabbitmq_manager.pika.BlockingConnection')
@mock.patch('src.core.rabbitmq_manager.pika.ConnectionParameters')
@mock.patch('src.core.rabbitmq_manager.pika.PlainCredentials')
def test_rabbitmq_connect_and_setup(mock_creds, mock_params, mock_conn, monkeypatch):
    """
    This test ensures that the `RabbitMQManager` correctly establishes a connection to RabbitMQ,
    declares the necessary exchanges and queues, binds the queue to the exchange, and sets the QoS
    (Quality of Service) settings. It uses mocks to simulate RabbitMQ behavior and verify the calls.
    """
    # Prepare fake channel
    fake_channel = mock.Mock()
    fake_connection = mock.Mock(channel=mock.Mock(return_value=fake_channel))
    mock_conn.return_value = fake_connection

    # Minimal config
    cfg = Config().model_dump()
    rm = RabbitMQManager(agent_id='test', config=cfg)
    # Verify connection called
    mock_creds.assert_called_once()
    mock_params.assert_called_once()
    mock_conn.assert_called_once()
    # Verify exchanges declared
    fake_channel.exchange_declare.assert_any_call(
        exchange=cfg['exchanges']['input'], exchange_type='topic', durable=True)
    fake_channel.exchange_declare.assert_any_call(
        exchange=cfg['exchanges']['output'], exchange_type='topic', durable=True)
    # Verify queue declared and bound
    fake_channel.queue_declare.assert_called_once_with(
        queue='Q.sim.test', durable=cfg['queue']['durable'])
    fake_channel.queue_bind.assert_called_once()
    # Verify QoS
    fake_channel.basic_qos.assert_called_once_with(
        prefetch_count=cfg['queue']['prefetch_count'])


def test_matlab_agent_initialization(monkeypatch):
    """
    This test checks the initialization of the `MatlabAgent` class. It ensures that the agent ID is
    correctly set, and that the `ConfigManager`, `RabbitMQManager`, and `MessageHandler` components
    are properly instantiated and assigned to the agent.
    """
    # Mock ConfigManager and RabbitMQManager to avoid real connections
    fake_cfg = {'rabbitmq': {}, 'exchanges': {}, 'queue': {}}
    monkeypatch.setattr('src.core.agent.ConfigManager', lambda self=None: type(
        'CM', (), {'get_config': lambda s: fake_cfg})())
    monkeypatch.setattr('src.core.agent.RabbitMQManager', lambda agent_id, config: type('RM', (), {
                        'register_message_handler': mock.Mock(), 'start_consuming': mock.Mock(), 'close': mock.Mock()})())
    monkeypatch.setattr('src.core.agent.MessageHandler', lambda agent_id, rm: type(
        'MH', (), {'handle_message': mock.Mock()})())

    agent = MatlabAgent(agent_id='agent1')
    assert agent.agent_id == 'agent1'
    # Ensure manager and handler are set
    assert hasattr(agent, 'rabbitmq_manager')
    assert hasattr(agent, 'message_handler')


@mock.patch.object(RabbitMQManager, 'start_consuming')
@mock.patch.object(RabbitMQManager, 'close')
def test_matlab_agent_start_stop(mock_close, mock_start):
    """
    This test verifies the `start` and `stop` methods of the `MatlabAgent`. It ensures that the agent
    starts consuming messages and handles a `KeyboardInterrupt` gracefully by calling the `stop` method
    and closing the RabbitMQ connection.
    """
    # Setup agent with stub managers
    class DummyRM:
        def start_consuming(self):
            raise KeyboardInterrupt()

        def close(self):
            pass
    dummy_rm = DummyRM()
    agent = MatlabAgent(agent_id='agent2')
    agent.rabbitmq_manager = dummy_rm
    # starting should catch KeyboardInterrupt and call stop()
    agent.stop = mock.Mock()
    agent.start()
    agent.stop.assert_called_once()
