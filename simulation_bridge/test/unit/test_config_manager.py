"""Unit tests for simulation_bridge.src.utils.config_manager module."""

from unittest import mock

import pytest
from pydantic import ValidationError

from simulation_bridge.src.utils import config_manager

# pylint: disable=too-many-arguments,unused-argument,protected-access,redefined-outer-name,line-too-long


@pytest.fixture
def sample_valid_config_dict(dummy_credentials):
    """Fixture che fornisce un dizionario di configurazione valido di esempio."""
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
            "keyfile": "/path/to/key.pem"
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
    """Fixture che sostituisce il logger con un mock."""
    logger = mock.Mock()
    monkeypatch.setattr(config_manager, "logger", logger)
    return logger


@pytest.fixture
def load_config_mock(monkeypatch):
    """Fixture che sostituisce load_config con un mock."""
    patcher = mock.patch(
        "simulation_bridge.src.utils.config_manager.load_config")
    yield patcher.start()
    patcher.stop()


class TestConfigManagerInit:
    """Test per il costruttore di ConfigManager e casi di caricamento config."""

    def test_init_loads_valid_config(
            self, sample_valid_config_dict, load_config_mock):
        """Verifica che ConfigManager carichi correttamente una config valida."""
        load_config_mock.return_value = sample_valid_config_dict

        manager = config_manager.ConfigManager("fake_path.yaml")

        assert manager.config == manager._validate_config(
            sample_valid_config_dict)
        load_config_mock.assert_called_once_with(manager.config_path)

    def test_init_fallback_default_on_file_not_found(
            self, load_config_mock, logger_mock):
        """Se il file non esiste, deve loggare warning e usare config di default."""
        load_config_mock.side_effect = FileNotFoundError("file missing")

        manager = config_manager.ConfigManager("missing.yaml")

        logger_mock.warning.assert_called_once()
        assert manager.config == manager.get_default_config()

    def test_init_fallback_default_on_validation_error(
            self, load_config_mock, logger_mock):
        """Se la validazione fallisce, logga errore e usa config di default."""
        load_config_mock.return_value = {"invalid": "data"}

        with pytest.raises(ValidationError):
            config_manager.ConfigManager._validate_config(
                config_manager.ConfigManager, {"invalid": "data"}
            )

        manager = config_manager.ConfigManager("bad.yaml")

        logger_mock.error.assert_called()
        assert manager.config == manager.get_default_config()


class TestConfigManagerValidate:
    """Test specifici per il metodo di validazione config."""

    def test_validate_config_returns_validated_dict(
            self, sample_valid_config_dict):
        """Verifica che _validate_config converta e ritorni dict validato."""
        validated = config_manager.ConfigManager._validate_config(
            config_manager.ConfigManager, sample_valid_config_dict
        )
        assert isinstance(validated, dict)
        assert "simulation_bridge" in validated
        assert validated["simulation_bridge"]["bridge_id"] == "test_bridge"

    def test_validate_config_raises_on_invalid_data(self):
        """Verifica che _validate_config lanci ValidationError se i dati sono invalidi."""
        invalid_data = {"rabbitmq": {"port": "not_an_int"}}
        with pytest.raises(ValidationError):
            config_manager.ConfigManager._validate_config(
                config_manager.ConfigManager, invalid_data
            )


class TestConfigManagerGetters:
    """Test per i metodi getter di ConfigManager."""

    @pytest.fixture
    def manager_with_config(self, sample_valid_config_dict, load_config_mock):
        """Istanzia ConfigManager con config valida mockata."""
        load_config_mock.return_value = sample_valid_config_dict
        manager = config_manager.ConfigManager("dummy.yaml")
        return manager

    def test_get_config_returns_full_config(self, manager_with_config):
        """get_config deve restituire il dict di configurazione completo."""
        config = manager_with_config.get_config()
        assert isinstance(config, dict)
        assert "rabbitmq" in config

    def test_get_rabbitmq_config_returns_rabbitmq_section(
            self, manager_with_config):
        """get_rabbitmq_config ritorna la sezione RabbitMQ."""
        rabbit = manager_with_config.get_rabbitmq_config()
        assert rabbit.get("host") == "localhost"

    def test_get_mqtt_config_returns_mqtt_section(self, manager_with_config):
        """get_mqtt_config ritorna la sezione MQTT."""
        mqtt = manager_with_config.get_mqtt_config()
        assert mqtt.get("host") == "mqtt.local"

    def test_get_rest_config_returns_rest_section(self, manager_with_config):
        """get_rest_config ritorna la sezione REST."""
        rest = manager_with_config.get_rest_config()
        assert rest.get("host") == "127.0.0.1"

    def test_get_logging_config_returns_logging_section(
            self, manager_with_config):
        """get_logging_config ritorna la sezione Logging."""
        log = manager_with_config.get_logging_config()
        assert log.get("level") == "INFO"


class TestConfigManagerErrorHandling:
    """Test su gestione errori inattesi durante l'inizializzazione."""

    def test_init_handles_ioerror_and_uses_default(
            self, load_config_mock, logger_mock):
        """IOError causa logging error e uso di configurazione default."""
        load_config_mock.side_effect = IOError("disk error")

        manager = config_manager.ConfigManager("any.yaml")

        logger_mock.error.assert_called()
        assert manager.config == manager.get_default_config()

    def test_init_handles_generic_exception_and_uses_default(
            self, load_config_mock, logger_mock):
        """Eccezione generica viene gestita con logging e config default."""
        load_config_mock.side_effect = Exception("unexpected")

        manager = config_manager.ConfigManager("any.yaml")

        logger_mock.error.assert_called()
        logger_mock.exception.assert_called()
        assert manager.config == manager.get_default_config()
