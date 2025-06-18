"""Test suite for MQTT Client using pytest and unittest.mock."""

# pylint: disable=too-many-arguments,unused-argument,protected-access,redefined-outer-name

import json
from unittest.mock import MagicMock
import pytest
from simulation_bridge.resources.mqtt import mqtt_client


@pytest.fixture
def mock_config():
    """Fixture to provide mock MQTT configuration."""
    return {
        'mqtt': {
            'host': 'localhost',
            'port': 1883,
            'keepalive': 60,
            'input_topic': 'test/input',
            'output_topic': 'test/output',
            'qos': 1
        },
        'payload_file': 'test_payload.yaml'
    }


@pytest.fixture
def client(mock_config):
    """Fixture to create an MQTTClient instance."""
    return mqtt_client.MQTTClient(mock_config)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self, tmp_path, monkeypatch):
        """Test loading a valid YAML config."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("mqtt:\n  host: test\n", encoding='utf-8')

        config = mqtt_client.load_config(str(config_path))
        assert config["mqtt"]["host"] == "test"

    def test_file_not_found_exits(self, capsys):
        """Test SystemExit is raised when config file is missing."""
        with pytest.raises(SystemExit):
            mqtt_client.load_config("missing.yaml")
        out, _ = capsys.readouterr()
        assert "Configuration file 'missing.yaml' not found." in out

    def test_yaml_error_exits(self, tmp_path, capsys):
        """Test SystemExit is raised on invalid YAML content."""
        config_path = tmp_path / "invalid.yaml"
        config_path.write_text("::: invalid :::", encoding="utf-8")

        with pytest.raises(SystemExit):
            mqtt_client.load_config(str(config_path))
        out, _ = capsys.readouterr()
        assert "Error parsing YAML file:" in out


class TestMQTTClientInit:  # pylint: disable=too-few-public-methods
    """Tests for MQTTClient initialization."""

    def test_initializes_client_attributes(self, mock_config):
        """Test that MQTTClient sets config and callbacks correctly."""
        client = mqtt_client.MQTTClient(mock_config)
        assert client.config['host'] == 'localhost'
        assert client.payload_file == 'test_payload.yaml'
        assert client.client.on_message == client.on_message  # pylint: disable=comparison-with-callable


class TestCreateRequest:
    """Tests for the create_request method."""

    def test_loads_payload_successfully(
            self, tmp_path, mock_config, monkeypatch):
        """Test create_request loads a YAML payload correctly."""
        payload_content = {'a': 1}
        payload_path = tmp_path / "test_payload.yaml"
        payload_path.write_text("a: 1", encoding="utf-8")

        monkeypatch.setattr(mqtt_client, '__file__', str(payload_path))
        mock_config['payload_file'] = 'test_payload.yaml'

        client = mqtt_client.MQTTClient(mock_config)
        result = client.create_request()
        assert result == payload_content

    def test_payload_file_missing_raises_exit(self, monkeypatch, mock_config):
        """Test SystemExit when payload file is missing or unreadable."""
        mock_config['payload_file'] = 'nonexistent.yaml'
        monkeypatch.setattr(mqtt_client, '__file__', '/fake/path/client.py')

        client = mqtt_client.MQTTClient(mock_config)
        with pytest.raises(SystemExit):
            client.create_request()


class TestConnectAndListen:  # pylint: disable=too-few-public-methods
    """Tests for connect_and_listen method."""

    def test_connects_and_publishes(self, client, monkeypatch):
        """Test MQTT client connects, subscribes, publishes and loops."""
        fake_payload = {"data": 123}
        client.create_request = MagicMock(return_value=fake_payload)

        client.client.connect = MagicMock()
        client.client.subscribe = MagicMock()
        client.client.publish = MagicMock()
        client.client.loop_forever = MagicMock()

        client.connect_and_listen()

        client.client.connect.assert_called_once_with('localhost', 1883, 60)
        client.client.subscribe.assert_called_once_with('test/output', qos=1)
        client.client.publish.assert_called_once_with(
            'test/input', json.dumps(fake_payload), qos=1
        )
        client.client.loop_forever.assert_called_once()


class TestOnMessage:  # pylint: disable=too-few-public-methods
    """Tests for on_message callback."""

    def test_prints_received_message(self, capsys, client):
        """Test that on_message prints topic and decoded payload."""
        msg = MagicMock()
        msg.topic = "some/topic"
        msg.payload = b'{"value": 42}'

        client.on_message(None, None, msg)
        out, _ = capsys.readouterr()

        assert "Message received:" in out
        assert "some/topic" in out
        assert '{"value": 42}' in out
