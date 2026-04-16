"""Unit tests for simulation_bridge.src.utils.config_manager module."""

from unittest import mock

import pytest
from pydantic import ValidationError

from simulation_bridge.src.utils import config_manager

# pylint: disable=too-many-arguments,unused-argument,protected-access,redefined-outer-name,line-too-long


@pytest.fixture
def sample_valid_config_dict(dummy_credentials):
    """Fixture that provides a sample valid configuration dictionary."""
    return {
        "simulation_bridge": {"bridge_id": "test_bridge"},
        "rabbitmq": {
            "host": "localhost",
            "port": 5672,
            "vhost": "/",
            "username": dummy_credentials['guest']['username'],
            "password": dummy_credentials['guest']['password'],
            "tls": False,
            "infrastructure": {
                "exchanges": [],
                "queues": [],
                "bindings": []
            }
        },
        "mqtt": {
            "host": "mqtt.local",
            "port": 1883,
            "keepalive": 60,
            "input_topic": "input",
            "output_topic": "output",
            "qos": 1,
            "username": dummy_credentials['user']['username'],
            "password": dummy_credentials['user']['password'],
            "tls": False
        },
        "rest": {
            "host": "127.0.0.1",
            "port": 8000,
            "endpoint": "/api",
            "debug": False,
            "certfile": "/path/to/cert.pem",
            "keyfile": "/path/to/key.pem",
            "jwt": {
                "secret": "your_jwt_secret",
                "algorithm": "HS256",
                "max_token_age_seconds": 3600
            }
        },
        "logging": {
            "level": "INFO",
            "format": "%(message)s",
            "file": "logfile.log"
        },
        "performance": {
            "enabled": False,
            "file": "performance_logs/performance_metrics.csv"
        }
    }


@pytest.fixture
def logger_mock(monkeypatch):
    """Fixture that replaces the logger with a mock."""
    logger = mock.Mock()
    monkeypatch.setattr(config_manager, "logger", logger)
    return logger


@pytest.fixture
def load_config_mock(monkeypatch):
    """Fixture that replaces load_config with a mock."""
    patcher = mock.patch(
        "simulation_bridge.src.utils.config_manager.load_config")
    yield patcher.start()
    patcher.stop()


class TestConfigManagerInit:
    """Tests for ConfigManager constructor and config loading cases."""

    def test_init_loads_valid_config(
            self, sample_valid_config_dict, load_config_mock):
        """Verifies that ConfigManager correctly loads a valid config."""
        load_config_mock.return_value = sample_valid_config_dict

        manager = config_manager.ConfigManager("fake_path.yaml")

        assert manager.config == manager._validate_config(
            sample_valid_config_dict)
        load_config_mock.assert_called_once_with(manager.config_path)

    def test_init_fallback_default_on_file_not_found(
            self, load_config_mock, logger_mock):
        """If file doesn't exist, should log warning and use default config."""
        load_config_mock.side_effect = FileNotFoundError("file missing")

        manager = config_manager.ConfigManager("missing.yaml")

        logger_mock.warning.assert_called_once()
        assert manager.config == manager.get_default_config()

    def test_init_fallback_default_on_validation_error(
            self, load_config_mock, logger_mock):
        """If validation fails, log error and use default config."""
        load_config_mock.return_value = {"invalid": "data"}

        with pytest.raises(ValidationError):
            config_manager.ConfigManager._validate_config(
                config_manager.ConfigManager, {"invalid": "data"}
            )

        manager = config_manager.ConfigManager("bad.yaml")

        logger_mock.error.assert_called()
        assert manager.config == manager.get_default_config()


class TestConfigManagerValidate:
    """Specific tests for the config validation method."""

    def test_validate_config_returns_validated_dict(
            self, sample_valid_config_dict):
        """Verifies that _validate_config converts and returns validated dict."""
        validated = config_manager.ConfigManager._validate_config(
            config_manager.ConfigManager, sample_valid_config_dict
        )
        assert isinstance(validated, dict)
        assert "simulation_bridge" in validated
        assert validated["simulation_bridge"]["bridge_id"] == "test_bridge"

    def test_validate_config_raises_on_invalid_data(self):
        """Verifies that _validate_config raises ValidationError if data is invalid."""
        invalid_data = {"rabbitmq": {"port": "not_an_int"}}
        with pytest.raises(ValidationError):
            config_manager.ConfigManager._validate_config(
                config_manager.ConfigManager, invalid_data
            )


class TestConfigManagerGetters:
    """Tests for ConfigManager getter methods."""

    @pytest.fixture
    def manager_with_config(self, sample_valid_config_dict, load_config_mock):
        """Instantiates ConfigManager with mocked valid config."""
        load_config_mock.return_value = sample_valid_config_dict
        manager = config_manager.ConfigManager("dummy.yaml")
        return manager

    def test_get_config_returns_full_config(self, manager_with_config):
        """get_config should return the complete configuration dict."""
        config = manager_with_config.get_config()
        assert isinstance(config, dict)
        assert "rabbitmq" in config

    def test_get_rabbitmq_config_returns_rabbitmq_section(
            self, manager_with_config):
        """get_rabbitmq_config returns the RabbitMQ section."""
        rabbit = manager_with_config.get_rabbitmq_config()
        assert rabbit.get("host") == "localhost"

    def test_get_mqtt_config_returns_mqtt_section(self, manager_with_config):
        """get_mqtt_config returns the MQTT section."""
        mqtt = manager_with_config.get_mqtt_config()
        assert mqtt.get("host") == "mqtt.local"

    def test_get_rest_config_returns_rest_section(self, manager_with_config):
        """get_rest_config returns the REST section."""
        rest = manager_with_config.get_rest_config()
        assert rest.get("host") == "127.0.0.1"

    def test_get_logging_config_returns_logging_section(
            self, manager_with_config):
        """get_logging_config returns the Logging section."""
        log = manager_with_config.get_logging_config()
        assert log.get("level") == "INFO"


class TestConfigManagerErrorHandling:
    """Tests on handling unexpected errors during initialization."""

    def test_init_handles_ioerror_and_uses_default(
            self, load_config_mock, logger_mock):
        """IOError causes error logging and use of default configuration."""
        load_config_mock.side_effect = IOError("disk error")

        manager = config_manager.ConfigManager("any.yaml")

        logger_mock.error.assert_called()
        assert manager.config == manager.get_default_config()

    def test_init_handles_generic_exception_and_uses_default(
            self, load_config_mock, logger_mock):
        """Generic exception is handled with logging and default config."""
        load_config_mock.side_effect = Exception("unexpected")

        manager = config_manager.ConfigManager("any.yaml")

        logger_mock.error.assert_called()
        logger_mock.exception.assert_called()
        assert manager.config == manager.get_default_config()


class TestRoutingConfigDefaults:
    """Tests for RoutingConfig Pydantic model defaults."""

    def test_routing_config_defaults(self):
        """RoutingConfig has correct defaults when not provided."""
        rc = config_manager.RoutingConfig()
        assert rc.max_timeout_seconds == 1200
        assert rc.min_timeout_seconds == 30

    def test_routing_config_custom_values(self):
        """RoutingConfig accepts custom values."""
        rc = config_manager.RoutingConfig(
            max_timeout_seconds=3600,
            min_timeout_seconds=300)
        assert rc.max_timeout_seconds == 3600
        assert rc.min_timeout_seconds == 300

    def test_simulation_bridge_config_includes_routing(self):
        """SimulationBridgeConfig includes routing with defaults."""
        sbc = config_manager.SimulationBridgeConfig(
            bridge_id='test')
        assert sbc.routing.max_timeout_seconds == 1200
        assert sbc.routing.min_timeout_seconds == 30

    def test_config_from_dict_with_routing(
            self, sample_valid_config_dict, load_config_mock):
        """Config.from_dict parses routing section correctly."""
        sample_valid_config_dict['simulation_bridge']['routing'] = {
            'max_timeout_seconds': 900,
            'min_timeout_seconds': 120,
        }
        load_config_mock.return_value = sample_valid_config_dict
        mgr = config_manager.ConfigManager("dummy.yaml")
        cfg = mgr.get_config()
        routing = cfg['simulation_bridge']['routing']
        assert routing['max_timeout_seconds'] == 900
        assert routing['min_timeout_seconds'] == 120
