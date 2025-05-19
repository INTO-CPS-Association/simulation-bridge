"""Unit tests for the config loader module with improved structure."""

import os
import pytest
from pathlib import Path
from importlib import resources
from unittest.mock import patch, mock_open

import yaml
from src.utils.config_loader import (
    DEFAULT_CONFIG_PATH,
    _substitute_env_vars,
    get_base_dir,
    get_config_value,
    load_config
)


@pytest.fixture
def sample_config_dict():
    """Return a sample configuration dictionary for testing."""
    return {
        "agent": {
            "agent_id": "matlab"
        },
        "rabbitmq": {
            "host": "localhost",
            "port": 5672,
            "username": "guest",
            "password": "guest"
        },
        "nested": {
            "deep": {
                "value": 42
            }
        }
    }


@pytest.fixture
def sample_yaml_content():
    """Return sample YAML content for testing."""
    return """
    agent:
      agent_id: matlab
    rabbitmq:
      host: "${HOSTNAME:localhost}"
      port: 5672
      username: "${USERNAME:guest}"
      password: "${PASSWORD:guest}"
    nested:
      deep:
        value: 42
    """


@pytest.fixture
def mock_existing_file(tmp_path, sample_yaml_content):
    """Create a temporary YAML file with sample content."""
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(sample_yaml_content)
    return yaml_file


class TestBaseDirRetrieval:
    """Tests for the get_base_dir function."""

    def test_get_base_dir_with_existing_dir(self, tmp_path, monkeypatch):
        """Test get_base_dir when the directory exists."""
        # Mock Path.exists to return True for our test path

        def mock_exists(self):
            return str(self) == str(tmp_path)

        monkeypatch.setattr(Path, "exists", mock_exists)

        # Mock cwd to return our test path if needed
        monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: tmp_path))

        # Test the function
        result = get_base_dir()
        assert result == tmp_path

    def test_get_base_dir_defaults_to_cwd(self, tmp_path, monkeypatch):
        """Test get_base_dir falls back to current working directory."""
        # Mock Path.exists to always return False
        monkeypatch.setattr(Path, "exists", lambda self: False)

        # Mock cwd to return our test path
        monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: tmp_path))

        # Test the function
        result = get_base_dir()
        assert result == tmp_path


class TestConfigLoading:
    """Tests for the load_config function."""

    def test_load_config_file_not_found(self, tmp_path):
        """Test that load_config raises FileNotFoundError when file is missing."""
        missing_file = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError) as exc_info:
            load_config(str(missing_file))
        assert "Configuration file not found" in str(exc_info.value)

    def test_load_config_yaml_error(self, tmp_path):
        """Test that load_config raises YAMLError when the YAML is invalid."""
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("invalid: yaml: ::::")

        with patch('yaml.load') as mock_yaml_load:
            mock_yaml_load.side_effect = yaml.YAMLError("YAML parsing error")
            with pytest.raises(yaml.YAMLError):
                load_config(str(invalid_yaml))

    def test_load_config_success(self, mock_existing_file, sample_config_dict):
        """Test successful config loading."""
        # Patch the environment variable substitution to return our dict
        with patch('src.utils.config_loader._substitute_env_vars',
                   return_value=sample_config_dict):
            result = load_config(str(mock_existing_file))
            assert result == sample_config_dict
            assert result["agent"]["agent_id"] == "matlab"
            assert result["rabbitmq"]["host"] == "localhost"
            assert result["nested"]["deep"]["value"] == 42

    def test_default_config_path_handling(self):
        """Test handling of the DEFAULT_CONFIG_PATH."""
        # Verify that DEFAULT_CONFIG_PATH is a Path object
        assert isinstance(DEFAULT_CONFIG_PATH, Path)

        # Test when the default config file is not found
        with patch('importlib.resources.open_text') as mock_open_text:
            mock_open_text.side_effect = FileNotFoundError(
                "Default configuration file not found inside the package."
            )

            with pytest.raises(FileNotFoundError) as exc_info:
                load_config()

            assert "Default configuration file not found inside the package." in str(
                exc_info.value)


class TestEnvironmentVariableSubstitution:
    """Tests for environment variable substitution in configs."""

    def test_substitute_env_vars_direct(self):
        """Test direct substitution of environment variables in a dictionary."""
        # Setup test environment
        os.environ.pop("TEST_VAR1", None)  # Make sure it doesn't exist
        os.environ["TEST_VAR2"] = "value2"

        # Create test config
        test_config = {
            "simple": "plain",
            "with_default": "${TEST_VAR1:default1}",
            "with_env": "${TEST_VAR2}",
            "nested": ["${TEST_VAR1:nested_default}", "${TEST_VAR2}"],
            "deep": {
                "object": "${TEST_VAR1:deep_default}"
            }
        }

        # Perform substitution
        result = _substitute_env_vars(test_config)

        # Verify results
        assert result["simple"] == "plain"
        assert result["with_default"] == "default1"  # Uses default value
        assert result["with_env"] == "value2"        # Uses environment value
        assert result["nested"][0] == "nested_default"
        assert result["nested"][1] == "value2"
        assert result["deep"]["object"] == "deep_default"

        # Cleanup
        os.environ.pop("TEST_VAR2", None)

    def test_env_substitution_in_config(self, tmp_path):
        """Test environment variable substitution when loading a config file."""
        # Create a test config with environment variables
        config_content = """
        host: "${HOST:default_host}"
        port: "${PORT:1234}"
        """
        config_file = tmp_path / "env_config.yaml"
        config_file.write_text(config_content)

        # Set test environment variable
        os.environ["HOST"] = "test_host"

        # Load the config
        result = load_config(str(config_file))

        # Verify substitution
        assert result["host"] == "test_host"      # Uses environment value
        assert result["port"] == "1234"           # Uses default value

        # Cleanup
        os.environ.pop("HOST", None)


class TestConfigValueRetrieval:
    """Tests for the get_config_value function."""

    def test_get_existing_values(self, sample_config_dict):
        """Test retrieving existing values from a config dictionary."""
        # Test top-level keys
        assert get_config_value(
            sample_config_dict, "agent") == {
            "agent_id": "matlab"}

        # Test nested keys with dot notation
        assert get_config_value(
            sample_config_dict,
            "agent.agent_id") == "matlab"
        assert get_config_value(
            sample_config_dict,
            "rabbitmq.host") == "localhost"
        assert get_config_value(sample_config_dict, "nested.deep.value") == 42

    def test_get_missing_values_with_default(self, sample_config_dict):
        """Test retrieving missing values with default values."""
        # Test with default for missing keys
        assert get_config_value(
            sample_config_dict,
            "nonexistent",
            default="default") == "default"
        assert get_config_value(
            sample_config_dict,
            "agent.missing",
            default=123) == 123
        assert get_config_value(
            sample_config_dict,
            "nested.nonexistent.key",
            default={}) == {}

    def test_get_missing_values_without_default(self, sample_config_dict):
        """Test retrieving missing values without specifying defaults."""
        # When no default is provided, should return None
        assert get_config_value(sample_config_dict, "nonexistent") is None
        assert get_config_value(sample_config_dict, "nested.missing") is None
