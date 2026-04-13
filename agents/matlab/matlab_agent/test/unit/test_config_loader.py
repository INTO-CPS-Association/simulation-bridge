"""Unit tests for shared config loader utilities used by MATLAB agent."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from base_agent.utils.config_loader import (
    default_config_path,
    get_base_dir,
    get_config_value,
    load_config,
    substitute_env_vars,
)


@pytest.fixture
def sample_config_dict(dummy_credentials):
    """Return a sample configuration dictionary for testing."""
    rabbit_creds = dummy_credentials.get("rabbitmq", {})
    return {
        "agent": {"agent_id": "matlab"},
        "rabbitmq": {
            "host": "localhost",
            "port": 5672,
            "username": rabbit_creds.get("username", "guest"),
            "password": rabbit_creds.get("password", "guest"),
        },
        "nested": {"deep": {"value": 42}},
    }


@pytest.fixture
def sample_yaml_content(dummy_credentials):
    """Return sample YAML content for testing."""
    rabbit_creds = dummy_credentials.get("rabbitmq", {})
    return f"""
agent:
  agent_id: matlab
rabbitmq:
  host: "{rabbit_creds.get("host", "localhost")}"
  port: {rabbit_creds.get("port", 5672)}
  username: "{rabbit_creds.get("username", "guest")}"
  password: "{rabbit_creds.get("password", "guest")}"
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

        def mock_exists(self):  # noqa: ANN001
            return str(self) == str(tmp_path)

        monkeypatch.setattr(Path, "exists", mock_exists)
        monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: tmp_path))
        assert get_base_dir() == tmp_path

    def test_get_base_dir_defaults_to_cwd(self, tmp_path, monkeypatch):
        """Test get_base_dir falls back to current working directory."""
        monkeypatch.setattr(Path, "exists", lambda self: False)
        monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: tmp_path))
        assert get_base_dir() == tmp_path


class TestConfigLoading:
    """Tests for the load_config function."""

    def test_load_config_file_not_found(self, tmp_path):
        """load_config raises FileNotFoundError when file is missing."""
        missing_file = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            load_config(
                package_name="matlab_agent",
                config_path=str(missing_file))

    def test_load_config_yaml_error(self, tmp_path):
        """load_config raises YAMLError when file content is invalid YAML."""
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("invalid: yaml: ::::")
        with pytest.raises(yaml.YAMLError):
            load_config(
                package_name="matlab_agent",
                config_path=str(invalid_yaml))

    def test_load_config_success(self, mock_existing_file, sample_config_dict):
        """load_config can load from explicit path and use custom substitution."""
        result = load_config(
            package_name="matlab_agent",
            config_path=str(mock_existing_file),
            substitute_func=lambda _: sample_config_dict,
        )
        assert result == sample_config_dict
        assert result["agent"]["agent_id"] == "matlab"
        assert result["rabbitmq"]["host"] == "localhost"
        assert result["nested"]["deep"]["value"] == 42

    def test_default_config_path(self):
        """default_config_path returns a valid Path for matlab_agent package."""
        path = default_config_path("matlab_agent")
        assert isinstance(path, Path)
        assert path.name == "config.yaml.template"

    def test_default_config_file_not_found(self):
        """load_config raises wrapped FileNotFoundError for missing package template."""
        with patch("base_agent.utils.config_loader.resources.open_text") as mock_open_text:
            mock_open_text.side_effect = FileNotFoundError("missing")
            with pytest.raises(
                FileNotFoundError,
                match="Default configuration file not found inside the package.",
            ):
                load_config(package_name="matlab_agent")


class TestEnvironmentVariableSubstitution:
    """Tests for environment variable substitution in configs."""

    def test_substitute_env_vars_direct(self):
        """Direct substitution works for dict/list/string structures."""
        os.environ.pop("TEST_VAR1", None)
        os.environ["TEST_VAR2"] = "value2"

        test_config = {
            "simple": "plain",
            "with_default": "${TEST_VAR1:default1}",
            "with_env": "${TEST_VAR2}",
            "nested": ["${TEST_VAR1:nested_default}", "${TEST_VAR2}"],
            "deep": {"object": "${TEST_VAR1:deep_default}"},
        }

        result = substitute_env_vars(test_config)
        assert result["simple"] == "plain"
        assert result["with_default"] == "default1"
        assert result["with_env"] == "value2"
        assert result["nested"][0] == "nested_default"
        assert result["nested"][1] == "value2"
        assert result["deep"]["object"] == "deep_default"

        os.environ.pop("TEST_VAR2", None)

    def test_env_substitution_in_config(self, tmp_path):
        """Substitution is applied when loading a config file."""
        config_content = """
host: "${HOST:default_host}"
port: "${PORT:1234}"
"""
        config_file = tmp_path / "env_config.yaml"
        config_file.write_text(config_content)
        os.environ["HOST"] = "test_host"

        result = load_config(
            package_name="matlab_agent",
            config_path=str(config_file),
        )
        assert result["host"] == "test_host"
        assert result["port"] == "1234"

        os.environ.pop("HOST", None)


class TestConfigValueRetrieval:
    """Tests for get_config_value utility."""

    def test_get_existing_values(self, sample_config_dict):
        """Reads top-level and nested values correctly."""
        assert get_config_value(
            sample_config_dict, "agent") == {
            "agent_id": "matlab"}
        assert get_config_value(
            sample_config_dict,
            "agent.agent_id") == "matlab"
        assert get_config_value(
            sample_config_dict,
            "rabbitmq.host") == "localhost"
        assert get_config_value(sample_config_dict, "nested.deep.value") == 42

    def test_get_missing_values_with_default(self, sample_config_dict):
        """Returns explicit defaults for missing values."""
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
        """Returns None when no default is provided."""
        assert get_config_value(sample_config_dict, "nonexistent") is None
        assert get_config_value(sample_config_dict, "nested.missing") is None
