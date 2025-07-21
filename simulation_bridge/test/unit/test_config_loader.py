# pylint: disable=redefined-outer-name
"""
test_config_loader.py - Unit tests for simulation_bridge.src.utils.config_loader

Tests for configuration loading utilities, focusing on file loading, environment
variable substitution, error handling, and protocol config loading.
"""

import io
from unittest import mock

import pytest

from simulation_bridge.src.utils import config_loader


@pytest.fixture
def sample_yaml():
    """Fixture providing sample YAML content."""
    return """
    database:
      host: localhost
      port: 5432
      user: ${DB_USER:defaultuser}
      password: ${DB_PASS:defaultpass}
    """


@pytest.fixture
def protocol_json():
    """Fixture providing sample protocol JSON content."""
    return {
        "protocols": [
            {"name": "proto1", "version": "1.0"},
            {"name": "proto2", "version": "2.0"},
        ]
    }


@pytest.fixture
def logger_mock():
    """Fixture mocking the logger."""
    with mock.patch("simulation_bridge.src.utils.config_loader.logger") as m_logger:
        yield m_logger


class TestLoadConfig:
    """Test cases for load_config function."""

    def test_load_default_config_success(
            self, sample_yaml, logger_mock, monkeypatch):
        """Test loading default config from package resources successfully."""
        mock_file = io.StringIO(sample_yaml)
        monkeypatch.setattr(
            "simulation_bridge.src.utils.config_loader.resources.open_text",
            lambda pkg, fname: mock_file
        )
        config = config_loader.load_config()
        assert config["database"]["host"] == "localhost"
        assert config["database"]["user"] == "defaultuser"
        logger_mock.debug.assert_called_with(
            "Loading default configuration file")

    def test_load_default_config_file_not_found(self, monkeypatch):
        """Test FileNotFoundError when default config file missing in package."""
        def raise_file_not_found(pkg, fname):
            raise FileNotFoundError

        monkeypatch.setattr(
            "simulation_bridge.src.utils.config_loader.resources.open_text",
            raise_file_not_found
        )
        with pytest.raises(FileNotFoundError, match="Default configuration file not found"):
            config_loader.load_config()

    def test_load_config_from_path_success(
            self, sample_yaml, tmp_path, logger_mock):
        """Test loading config from a specified path successfully."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(sample_yaml, encoding="utf-8")

        config = config_loader.load_config(str(config_file))
        assert config["database"]["port"] == 5432
        assert config["database"]["password"] == "defaultpass"
        logger_mock.debug.assert_called_with(
            "Loading configuration file from path: %s", str(config_file)
        )

    def test_load_config_file_not_found(self, tmp_path):
        """Test FileNotFoundError raised if config file path does not exist."""
        missing_path = tmp_path / "missing.yaml"
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            config_loader.load_config(str(missing_path))


class TestEnvVarSubstitution:
    """Test cases for _substitute_env_vars function."""

    # pylint: disable=protected-access

    def test_substitute_env_vars_dict_with_defaults(self, monkeypatch):
        """Test environment variables substitution with default values in dict."""
        config = {
            "path": "/data/${DATA_DIR:default_dir}",
            "nested": {"user": "${USER_NAME:anonymous}"}
        }
        monkeypatch.setenv("USER_NAME", "tester")
        result = config_loader._substitute_env_vars(config)
        assert result["path"] == "/data/default_dir"
        assert result["nested"]["user"] == "tester"

    def test_substitute_env_vars_list(self, monkeypatch):
        """Test substitution in list items."""
        config = ["${VAR1:def1}", "${VAR2:def2}", "no_substitution"]
        monkeypatch.setenv("VAR2", "value2")
        result = config_loader._substitute_env_vars(config)
        assert result == ["def1", "value2", "no_substitution"]

    def test_substitute_env_vars_string_no_env(self):
        """Test string without environment variables remains unchanged."""
        assert config_loader._substitute_env_vars(
            "plainstring") == "plainstring"

    def test_substitute_env_vars_partial_env_string(self, monkeypatch):
        """Test string with embedded environment variable replaced correctly."""
        monkeypatch.setenv("HOME", "/home/user")
        value = "Path is ${HOME}/folder"
        expected = "Path is /home/user/folder"
        assert config_loader._substitute_env_vars(value) == expected

    def test_substitute_env_vars_empty_default(self):
        """Test substitution with no default and unset env var results in empty string."""
        config = "${UNSET_ENV:}"
        assert config_loader._substitute_env_vars(config) == ""


class TestErrorHandling:
    """Test cases for exception and error handling."""

    def test_load_config_handles_yaml_error(self, tmp_path):
        """Test load_config raises yaml.YAMLError on invalid YAML content."""
        bad_yaml = "key: value: another"  # Invalid YAML syntax
        file_path = tmp_path / "bad.yaml"
        file_path.write_text(bad_yaml, encoding="utf-8")

        with pytest.raises(Exception) as exc_info:
            config_loader.load_config(str(file_path))
        assert "mapping values are not allowed" in str(exc_info.value) or \
               "could not find expected ':'" in str(exc_info.value)

    def test_load_config_handles_keyboard_interrupt(self, monkeypatch):
        """Test load_config propagates KeyboardInterrupt exceptions."""
        def raise_keyboard_interrupt(*args, **kwargs):
            raise KeyboardInterrupt

        monkeypatch.setattr(
            "simulation_bridge.src.utils.config_loader.resources.open_text",
            raise_keyboard_interrupt
        )

        with pytest.raises(KeyboardInterrupt):
            config_loader.load_config()
