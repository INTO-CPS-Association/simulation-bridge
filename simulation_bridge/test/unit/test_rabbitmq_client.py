"""Tests for RabbitMQ client in simulation bridge."""

# pylint: disable=too-many-arguments,unused-argument,protected-access,redefined-outer-name
# pylint: disable=too-many-positional-arguments
from unittest.mock import MagicMock
from unittest import mock
import pytest

from simulation_bridge.resources.rabbitmq import rabbitmq_client


@pytest.fixture
def mock_config():
    """Mock configuration dictionary for RabbitMQClient."""
    return {
        'rabbitmq':
            {
                'host': 'localhost',
                'port': 5672,
                'vhost': '/',
                'username': 'guest',
                'password': 'guest'
            },
        'digital_twin': {
            'dt_id': 'dt123',
            'routing_key_send': 'dt.send'
        },
        'exchanges': {
            'input_bridge': {
                'name': 'input_ex',
                'type': 'direct',
                'durable': True
            },
            'bridge_result': {
                'name': 'result_ex',
                'type': 'fanout',
                'durable': True
            }
        },
        'queue': {
            'result_queue_prefix': 'bridge',
            'durable': True,
            'routing_key': 'dt.result'
        },
        'payload_file': 'payload.yaml'
    }


@pytest.fixture
def mock_channel():
    """Mock channel object."""
    return MagicMock()


@pytest.fixture
def mock_connection(mock_channel):
    """Mock pika connection with mock channel."""
    conn = MagicMock()
    conn.channel.return_value = mock_channel
    return conn


@pytest.fixture
def mock_pika(monkeypatch, mock_connection):
    """Patch pika.BlockingConnection to return mock connection and avoid real connection errors."""
    monkeypatch.setattr(
        rabbitmq_client.pika,
        "BlockingConnection",
        lambda params: mock_connection
    )


class TestRabbitMQClientInitialization:  # pylint: disable=too-few-public-methods
    """Test RabbitMQClient initialization and infrastructure setup."""

    def test_initialization_sets_up_infrastructure(
            self, mock_config, mock_pika, mock_channel):
        """Ensure __init__ sets up exchanges, queues, and bindings correctly."""
        client = rabbitmq_client.RabbitMQClient(mock_config)

        assert client.dt_id == 'dt123'
        mock_channel.exchange_declare.assert_any_call(
            exchange='input_ex', exchange_type='direct', durable=True)
        mock_channel.exchange_declare.assert_any_call(
            exchange='result_ex', exchange_type='fanout', durable=True)
        mock_channel.queue_declare.assert_called_once()
        mock_channel.queue_bind.assert_called_once()


class TestSendSimulationRequest:  # pylint: disable=too-few-public-methods
    """Test the send_simulation_request method."""

    def test_send_simulation_request_calls_basic_publish(
        self, mock_config, mock_pika, mock_channel
    ):
        """Check that simulation request triggers a call to basic_publish."""
        client = rabbitmq_client.RabbitMQClient(mock_config)

        payload = {'temperature': 42}
        client.send_simulation_request(payload)

        mock_channel.basic_publish.assert_called_once()
        args, kwargs = mock_channel.basic_publish.call_args  # pylint: disable=unused-variable
        assert kwargs['exchange'] == 'input_ex'
        assert kwargs['routing_key'] == 'dt.send'
        assert 'temperature' in kwargs['body']


class TestHandleResult:
    """Test handling of incoming messages."""

    def test_handle_result_acknowledges_valid_yaml(
            self, mock_config, mock_pika, mock_channel):
        """Should acknowledge a valid YAML result message."""
        client = rabbitmq_client.RabbitMQClient(mock_config)

        method = MagicMock()
        method.routing_key = 'source.service'
        method.delivery_tag = 10
        body = b"key: value"

        client.handle_result(mock_channel, method, None, body)
        mock_channel.basic_ack.assert_called_once_with(10)

    def test_handle_result_handles_yaml_error(
            self, mock_config, mock_pika, mock_channel):
        """Should nack message if YAML is invalid."""
        client = rabbitmq_client.RabbitMQClient(mock_config)

        method = MagicMock()
        method.routing_key = 'source.service'
        method.delivery_tag = 11
        body = b": invalid_yaml"

        client.handle_result(mock_channel, method, None, body)
        mock_channel.basic_nack.assert_called_once_with(11)


class TestStartListening:  # pylint: disable=too-few-public-methods
    """Test listener behavior."""

    def test_start_listening_calls_basic_consume_and_start(self,
                                                           mock_config,
                                                           mock_pika,
                                                           mock_channel):
        """Ensure basic_consume and start_consuming are called."""
        client = rabbitmq_client.RabbitMQClient(mock_config)
        client.start_listening()

        mock_channel.basic_consume.assert_called_once()
        mock_channel.start_consuming.assert_called_once()


class TestYamlLoading:  # pylint: disable=too-few-public-methods
    """Test static YAML loading."""

    def test_load_yaml_file_returns_parsed_data(self, tmp_path):
        """Ensure load_yaml_file loads and parses YAML content."""
        file_path = tmp_path / "data.yaml"
        file_path.write_text("foo: bar", encoding="utf-8")

        result = rabbitmq_client.RabbitMQClient.load_yaml_file(str(file_path))
        assert result == {"foo": "bar"}


class TestLoadConfig:
    """Test the load_config function."""

    def test_load_config_success(self, tmp_path, monkeypatch):
        """Should return loaded config when file is valid."""
        config_path = tmp_path / "rabbitmq_use.yaml"
        config_path.write_text("a: 1", encoding="utf-8")

        monkeypatch.setattr(rabbitmq_client, "sys", mock.MagicMock())
        config = rabbitmq_client.load_config(str(config_path))
        assert config == {"a": 1}

    def test_load_config_file_not_found(self, monkeypatch):
        """Should exit if config file is missing."""
        mock_exit = mock.MagicMock()
        monkeypatch.setattr(
            rabbitmq_client,
            "sys",
            mock.MagicMock(
                exit=mock_exit))

        rabbitmq_client.load_config("nonexistent.yaml")
        mock_exit.assert_called_once_with(1)


class TestMainFunction:  # pylint: disable=too-few-public-methods
    """Test main function behavior and CLI entry."""

    @mock.patch("simulation_bridge.resources.rabbitmq.rabbitmq_client.RabbitMQClient")
    def test_main_keyboard_interrupt(
            self, mock_rmq_client, mock_config, monkeypatch, mock_pika):
        """Simulate KeyboardInterrupt in main."""
        monkeypatch.setattr(rabbitmq_client, "load_config", lambda: mock_config)
        monkeypatch.setattr(
            rabbitmq_client,
            "start_dt_listener",
            lambda config: None)
        monkeypatch.setattr(
            rabbitmq_client.time, "sleep", mock.Mock(
                side_effect=KeyboardInterrupt))

        rabbitmq_client.main()

        mock_rmq_client.assert_called_once_with(mock_config)

    @pytest.mark.parametrize("error_type",
                             [ValueError("fail"), OSError("fail")])
    @mock.patch("simulation_bridge.resources.rabbitmq.rabbitmq_client.RabbitMQClient")
    def test_main_unexpected_exceptions(
            self, mock_rmq_client, mock_config, monkeypatch, mock_pika, error_type):
        """Ensure main handles unexpected errors gracefully."""
        instance = mock_rmq_client.return_value
        instance.load_yaml_file.return_value = {}
        instance.send_simulation_request.side_effect = error_type

        monkeypatch.setattr(rabbitmq_client, "load_config", lambda: mock_config)
        monkeypatch.setattr(
            rabbitmq_client,
            "start_dt_listener",
            lambda config: None)
        monkeypatch.setattr(
            rabbitmq_client.time, "sleep", mock.Mock(
                side_effect=KeyboardInterrupt))

        rabbitmq_client.main()
