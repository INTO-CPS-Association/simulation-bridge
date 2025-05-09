import os
from importlib import resources
from pathlib import Path

import pytest
import yaml
from src.utils.config_loader import (DEFAULT_CONFIG_PATH, _substitute_env_vars,
                                     get_base_dir, get_config_value,
                                     load_config)
from yaml import YAMLError

# Test that `get_base_dir` returns the current working directory when no
# base directory exists


def test_get_base_dir_defaults_to_cwd(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "exists", lambda self: False)
    monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: tmp_path))
    result = get_base_dir()
    assert result == tmp_path

# Test that `load_config` raises FileNotFoundError when the configuration
# file is missing


def test_load_config_file_not_found(tmp_path):
    missing = tmp_path / "nope.yaml"
    with pytest.raises(FileNotFoundError) as exc:
        load_config(str(missing))
    assert "Configuration file not found" in str(exc.value)

# Test that `load_config` raises YAMLError when the YAML file is invalid


def test_load_config_yaml_error(tmp_path, monkeypatch):
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("not: yaml: ::::")
    monkeypatch.setattr(yaml, "load", lambda f, Loader: (
        _ for _ in ()).throw(YAMLError("bad")))
    with pytest.raises(YAMLError):
        load_config(str(cfg))

# Test that `load_config` substitutes environment variables in the
# configuration file


def test_load_config_env_substitution(tmp_path, monkeypatch):
    content = """
  host: "${HOSTNAME:default_host}"
  port: "${PORT:1234}"
  nested:
    - "a${VAR1}"
    - "${VAR2:val2}"
  """
    cfg = tmp_path / "good.yaml"
    cfg.write_text(content)
    monkeypatch.setenv("VAR1", "X")
    # VAR2 is not set, so the default value is used
    result = load_config(str(cfg))
    assert result["host"] == "default_host"
    assert result["port"] == "1234"
    assert result["nested"][0] == "aX"
    assert result["nested"][1] == "val2"

# Test that `_substitute_env_vars` substitutes environment variables in a
# dictionary


def test_substitute_env_vars_direct():
    cfg = {
        "a": "plain",
        "b": "${B:bee}",
        "c": ["x${C}", "y${D:dee}", {"e": "${E}"}],
    }
    os.environ.pop("B", None)
    os.environ["C"] = "see"
    result = _substitute_env_vars(cfg)
    assert result["a"] == "plain"
    assert result["b"] == "bee"
    assert result["c"][0] == "xsee"
    assert result["c"][1] == "ydee"
    assert result["c"][2]["e"] == ""

# Test that `get_config_value` retrieves existing values and defaults for
# missing keys


def test_get_config_value_existing_and_default():
    cfg = {"x": {"y": {"z": 10}}, "a": 1}
    assert get_config_value(cfg, "x.y.z") == 10
    assert get_config_value(cfg, "x.y") == {"z": 10}
    assert get_config_value(cfg, "a") == 1
    assert get_config_value(cfg, "x.missing", default="d") == "d"
    assert get_config_value(cfg, "nope", default=None) is None

# Test that `DEFAULT_CONFIG_PATH` is a valid path and raises an error if
# the file is missing


def test_default_config_path_points_somewhere(tmp_path, monkeypatch):
    assert isinstance(DEFAULT_CONFIG_PATH, Path)

    # 1️⃣ Monckeypatch di `resources.open_text` per simulare FileNotFoundError
    def mock_open_text(*args, **kwargs):
        raise FileNotFoundError(
            "Default configuration file not found inside the package.")

    monkeypatch.setattr(resources, "open_text", mock_open_text)

    # 2️⃣ Controlla se il FileNotFoundError viene sollevato correttamente
    with pytest.raises(FileNotFoundError, match="Default configuration file not found inside the package."):
        load_config()

# Test loading a YAML configuration file and verifying key values


def test_load_full_config_structure(tmp_path):
    """
    Load a sample YAML file with a predefined structure and verify key values.
    """
    sample = tmp_path / "config.yaml"
    sample.write_text("""
agent:
  agent_id: matlab

rabbitmq:
  host: localhost
  port: 5672
  username: guest
  password: guest
  heartbeat: 600

exchanges:
  input: ex.bridge.output
  output: ex.sim.result

queue:
  durable: true
  prefetch_count: 1

logging:
  level: INFO
  file: logs/matlab_agent.log

tcp:
  host: localhost
  port: 5678

response_templates:
  success:
    status: success
    simulation:
      type: batch
    timestamp_format: "%Y-%m-%dT%H:%M:%SZ"
    include_metadata: true
    metadata_fields:
      - execution_time
      - memory_usage
      - matlab_version
""")
    cfg = load_config(str(sample))
    # Verify key fields
    assert get_config_value(cfg, "agent.agent_id") == "matlab"
    assert get_config_value(cfg, "rabbitmq.port") == 5672
    assert get_config_value(cfg, "queue.durable") is True
    assert get_config_value(cfg, "logging.level") == "INFO"
    assert get_config_value(cfg, "tcp.port") == 5678
    # Verify nested list
    metadata = get_config_value(
        cfg, "response_templates.success.metadata_fields")
    assert isinstance(metadata, list)
    assert "execution_time" in metadata
    assert "matlab_version" in metadata
