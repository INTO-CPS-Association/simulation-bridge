"""
Test suite for the ConfigManager class.
"""
from pathlib import Path
import pytest
from unittest import mock
from pydantic import ValidationError
from agents.matlab.matlab_agent.src.utils.config_manager import ConfigManager


@pytest.fixture
def mock_config_data():
    """Fixture providing standard test configuration data."""
    return {
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
def mock_config_path():
    """Fixture providing a standard mock config path."""
    return "/fake/path/config.yaml"


@pytest.fixture
def mock_load_config(mock_config_data):
    """
    Fixture that patches the load_config function to return test configuration data.

    Args:
        mock_config_data: The test configuration data fixture

    Returns:
        The mocked load_config function
    """
    with mock.patch("src.core.config_manager.load_config") as mocked_load:
        mocked_load.return_value = mock_config_data
        yield mocked_load


@pytest.fixture
def mock_path_exists():
    """Fixture that patches Path.exists to always return True."""
    with mock.patch.object(Path, "exists", return_value=True):
        yield


@pytest.fixture
def config_manager(mock_config_path, mock_load_config, mock_path_exists):
    """
    Fixture that creates a pre-configured ConfigManager instance.

    Args:
        mock_config_path: The mock config path fixture
        mock_load_config: The mocked load_config function fixture
        mock_path_exists: The mocked Path.exists fixture

    Returns:
        A ConfigManager instance initialized with the test configuration
    """
    return ConfigManager(mock_config_path)


def test_config_manager_initialization(
        config_manager,
        mock_load_config,
        mock_config_path):
    """
    Test that ConfigManager initializes correctly with the provided configuration.

    Args:
        config_manager: The pre-configured ConfigManager fixture
        mock_load_config: The mocked load_config function fixture
        mock_config_path: The mock config path fixture
    """
    mock_load_config.assert_called_once_with(Path(mock_config_path))
    assert config_manager.config["agent"]["agent_id"] == "matlab"
    assert config_manager.config["rabbitmq"]["host"] == "localhost"


def test_get_default_config():
    """Test that default configuration values are correct."""
    manager = ConfigManager()
    default_config = manager.get_default_config()

    assert isinstance(default_config, dict)
    assert default_config["agent"]["agent_id"] == "matlab"
    assert default_config["rabbitmq"]["port"] == 5672


def test_get_config(config_manager):
    """
    Test that get_config returns the correct configuration values.

    Args:
        config_manager: The pre-configured ConfigManager fixture
    """
    config = config_manager.get_config()

    assert config["agent"]["agent_id"] == "matlab"
    assert config["rabbitmq"]["host"] == "localhost"


def test_validate_config_success(config_manager, mock_config_data):
    """
    Test that config validation succeeds with correct data.

    Args:
        config_manager: The pre-configured ConfigManager fixture
        mock_config_data: The test configuration data fixture
    """
    validated_config = config_manager._validate_config(mock_config_data)

    assert validated_config["agent"]["agent_id"] == "matlab"


def test_validate_config_failure():
    """Test that validation error is raised with invalid data."""
    manager = ConfigManager()
    invalid_config = {"rabbitmq": {"port": "not_a_number"}}

    with pytest.raises(ValidationError):
        manager._validate_config(invalid_config)


def test_initialization_with_invalid_path():
    """Test initialization when the configuration file does not exist."""
    with mock.patch.object(Path, "exists", return_value=False):
        manager = ConfigManager("/invalid/path/config.yaml")

        assert manager.config == manager.get_default_config()
