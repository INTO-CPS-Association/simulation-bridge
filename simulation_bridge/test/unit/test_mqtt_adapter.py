# simulation_bridge/test/unit/test_mqtt_adapter.py
# pylint: disable=too-many-arguments,unused-argument,protected-access,redefined-outer-name

"""Unit tests for the MQTTAdapter class using pytest and unittest.mock."""

from unittest.mock import MagicMock, patch
import pytest

from simulation_bridge.src.protocol_adapters.mqtt import mqtt_adapter


@pytest.fixture
def config_mock():
    """Fixture for MQTT configuration."""
    return {
        'host': 'localhost',
        'port': 1883,
        'keepalive': 60,
        'input_topic': 'test/input',
        'output_topic': 'test/output',
        'username': 'user',
        'password': 'pass',
        'qos': 1
    }


@pytest.fixture
def config_manager_mock(config_mock):
    """Fixture for mocked ConfigManager."""
    mock = MagicMock()
    mock.get_mqtt_config.return_value = config_mock
    return mock


@pytest.fixture
def adapter(config_manager_mock):
    """Fixture for MQTTAdapter instance."""
    with patch('simulation_bridge.src.protocol_adapters.mqtt.mqtt_adapter.mqtt.Client'):
        return mqtt_adapter.MQTTAdapter(config_manager_mock)


class TestMQTTAdapterInitialization:  # pylint: disable=too-few-public-methods
    """Tests for MQTTAdapter initialization."""

    def test_init_sets_client_config(self, config_manager_mock):
        """Should set username and password for both MQTT clients."""
        with patch('simulation_bridge.src.protocol_adapters.mqtt.mqtt_adapter.mqtt.Client') as client_mock:  # pylint: disable=line-too-long
            adapter = mqtt_adapter.MQTTAdapter(config_manager_mock)
            assert client_mock.return_value.username_pw_set.call_count == 2
            assert adapter.topic == 'test/input'
            assert adapter._running is False


class TestMQTTAdapterOnConnect:
    """Tests for on_connect behavior."""

    def test_on_connect_success(self, adapter):
        """Should subscribe to input topic on successful connect."""
        client = MagicMock()
        adapter.client = client  # internal client used in on_connect
        adapter.on_connect(client, None, None, rc=0)
        client.subscribe.assert_called_once_with('test/input')

    def test_on_connect_failure_logs_error(self, adapter, monkeypatch):
        """Should log error when connection fails."""
        logger_mock = MagicMock()
        monkeypatch.setattr(mqtt_adapter, 'logger', logger_mock)
        adapter.on_connect(MagicMock(), None, None, rc=1)
        logger_mock.error.assert_called_once()


class TestMQTTAdapterOnDisconnect:
    """Tests for on_disconnect behavior."""

    def test_on_disconnect_clean(self, adapter, monkeypatch):
        """Should log clean disconnect."""
        logger_mock = MagicMock()
        monkeypatch.setattr(mqtt_adapter, 'logger', logger_mock)
        adapter.on_disconnect(MagicMock(), None, rc=0)
        logger_mock.debug.assert_called_once()

    def test_on_disconnect_unexpected(self, adapter, monkeypatch):
        """Should log unexpected disconnect."""
        logger_mock = MagicMock()
        monkeypatch.setattr(mqtt_adapter, 'logger', logger_mock)
        adapter.on_disconnect(MagicMock(), None, rc=1)
        logger_mock.warning.assert_called_once()


class TestMQTTAdapterOnMessage:
    """Tests for message handling."""

    def test_on_message_valid_yaml(self, adapter, monkeypatch):
        """Should handle valid YAML message."""
        send_mock = MagicMock()
        signal_mock = MagicMock(return_value=MagicMock(send=send_mock))
        monkeypatch.setattr(mqtt_adapter, 'signal', signal_mock)

        payload = b"simulation:\n  client_id: test_client\n  simulator: test_sim"
        msg = MagicMock(payload=payload)

        adapter.on_message(None, None, msg)

        send_mock.assert_called_once()

    def test_on_message_invalid_payload(self, adapter, monkeypatch):
        """Should fallback to raw message on invalid JSON/YAML."""
        send_mock = MagicMock()
        signal_mock = MagicMock(return_value=MagicMock(send=send_mock))
        monkeypatch.setattr(mqtt_adapter, 'signal', signal_mock)

        msg = MagicMock(payload=b"not a valid format: }")

        adapter.on_message(None, None, msg)

        send_mock.assert_called_once()


class TestMQTTAdapterStartStop:
    """Tests for adapter start and stop behavior."""

    def test_start_creates_thread(self, adapter, monkeypatch):
        """Should start a client thread."""
        thread_mock = MagicMock()
        monkeypatch.setattr(
            mqtt_adapter.threading,
            'Thread',
            lambda **kwargs: thread_mock)
        adapter._run_client = MagicMock()

        adapter.start()
        assert adapter._running is True
        thread_mock.start.assert_called_once()

    def test_stop_disconnects_client(self, adapter):
        """Should disconnect client on stop."""
        client_mock = MagicMock()
        adapter.client = client_mock
        adapter.stop()
        client_mock.disconnect.assert_called_once()


class TestMQTTAdapterPublish:
    """Tests for sending messages."""

    def test_send_result_success(self, adapter):
        """Should publish message to output topic."""
        mqtt_client = MagicMock()
        adapter.mqtt_client = mqtt_client
        message = {'test': 'value'}

        adapter.send_result(message)
        mqtt_client.publish.assert_called_once()

    def test_publish_result_message_mqtt(self, adapter):
        """Should call send_result with message from kwargs."""
        adapter.send_result = MagicMock()
        adapter.publish_result_message_mqtt(None, message={'a': 1})
        adapter.send_result.assert_called_once_with({'a': 1})
