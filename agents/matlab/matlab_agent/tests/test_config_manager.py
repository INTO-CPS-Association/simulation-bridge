import pytest
from unittest import mock
from pathlib import Path
from src.core.config_manager import ConfigManager
from src.core.config_manager import Config
from pydantic import ValidationError

# Mock path for the configuration file
MOCK_CONFIG_PATH = "/fake/path/config.yaml"

# Example configuration
MOCK_CONFIG_DATA = {
    "agent": {"agent_id": "matlab"},
    "rabbitmq": {
        "host": "localhost",
        "port": 5672,
        "username": "guest",
        "password": "guest",
        "heartbeat": 600
    },
    "exchanges": {
        "input": "ex.bridge.output",
        "output": "ex.sim.result"
    },
    "queue": {
        "durable": True,
        "prefetch_count": 1
    },
    "logging": {
        "level": "INFO",
        "file": "logs/matlab_agent.log"
    },
    "tcp": {
        "host": "localhost",
        "port": 5678
    },
    "response_templates": {
        "success": {
            "status": "success",
            "simulation": {"type": "batch"},
            "timestamp_format": "%Y-%m-%dT%H:%M:%SZ",
            "include_metadata": True,
            "metadata_fields": ["execution_time", "memory_usage", "matlab_version"]
        },
        "error": {
            "status": "error",
            "include_stacktrace": False,
            "error_codes": {
                "invalid_config": 400,
                "matlab_start_failure": 500,
                "execution_error": 500,
                "timeout": 504,
                "missing_file": 404
            },
            "timestamp_format": "%Y-%m-%dT%H:%M:%SZ"
        },
        "progress": {
            "status": "in_progress",
            "include_percentage": True,
            "update_interval": 5,
            "timestamp_format": "%Y-%m-%dT%H:%M:%SZ"
        }
    }
}


@pytest.fixture
def mock_load_config():
    """ Mock for load_config that returns a configuration dictionary. """
    with mock.patch("src.core.config_manager.load_config") as mocked_load:
        mocked_load.return_value = MOCK_CONFIG_DATA
        yield mocked_load


@pytest.fixture
def mock_path_exists():
    """ Mock for Path.exists that returns True. """
    with mock.patch.object(Path, "exists", return_value=True):
        yield


def test_config_manager_initialization(mock_load_config, mock_path_exists):
    """
    Tests the initialization of the ConfigManager class.

    - Verifies that the `load_config` method is called once with the correct path.
    - Ensures the `agent_id` in the configuration is set to "matlab".
    - Confirms the RabbitMQ host in the configuration is set to "localhost".
    """
    """ Tests that ConfigManager is initialized correctly. """
    manager = ConfigManager(MOCK_CONFIG_PATH)
    mock_load_config.assert_called_once_with(Path(MOCK_CONFIG_PATH))
    assert manager.config["agent"]["agent_id"] == "matlab"
    assert manager.config["rabbitmq"]["host"] == "localhost"


def test_get_default_config():
    """ Tests that default values are correct. """
    manager = ConfigManager()
    default_config = manager.get_default_config()
    assert isinstance(default_config, dict)
    assert default_config["agent"]["agent_id"] == "matlab"
    assert default_config["rabbitmq"]["port"] == 5672


def test_get_config(mock_load_config, mock_path_exists):
    """ Tests that get_config returns the correct values. """
    manager = ConfigManager(MOCK_CONFIG_PATH)
    config = manager.get_config()
    assert config["agent"]["agent_id"] == "matlab"
    assert config["rabbitmq"]["host"] == "localhost"


def test_validate_config_success(mock_load_config):
    """ Tests that validation succeeds with correct data. """
    manager = ConfigManager(MOCK_CONFIG_PATH)
    validated_config = manager._validate_config(MOCK_CONFIG_DATA)
    assert validated_config["agent"]["agent_id"] == "matlab"


def test_validate_config_failure():
    """ Tests that a validation error is raised with invalid data. """
    manager = ConfigManager()
    with pytest.raises(ValidationError):
        manager._validate_config({"rabbitmq": {"port": "not_a_number"}})


def test_initialization_with_invalid_path():
    """ Tests initialization when the configuration file does not exist. """
    with mock.patch.object(Path, "exists", return_value=False):
        manager = ConfigManager("/invalid/path/config.yaml")
        assert manager.config == manager.get_default_config()
