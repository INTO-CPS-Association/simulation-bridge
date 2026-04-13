"""Tests for shared config-loader utilities."""

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


def test_default_config_path_missing_package_raises() -> None:
    """Unknown package should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        default_config_path("not_a_real_package")


def test_default_config_path_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Package resource path should be returned when template exists."""

    class FakeResource:
        """Minimal Traversable-like object for config template path testing."""

        def __init__(self, value: str) -> None:
            self._value = value

        def joinpath(self, *_parts: str):
            return self

        def is_file(self) -> bool:
            return True

        def __str__(self) -> str:
            return self._value

    monkeypatch.setattr(
        "base_agent.utils.config_loader.resources.files",
        lambda _pkg: FakeResource("/tmp/config.yaml.template"),
    )
    assert default_config_path("matlab_agent") == Path("/tmp/config.yaml.template")


def test_load_config_file_not_found(tmp_path: Path) -> None:
    """Missing config path should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("matlab_agent", tmp_path / "missing.yaml")


def test_load_config_from_explicit_file(tmp_path: Path) -> None:
    """Config should load and return parsed dict."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("root:\n  value: 1\n", encoding="utf-8")
    loaded = load_config("matlab_agent", config_file)
    assert loaded["root"]["value"] == 1


def test_load_config_uses_substitute_hook(tmp_path: Path) -> None:
    """Custom substitution hook should be honored."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("root:\n  value: 1\n", encoding="utf-8")
    loaded = load_config(
        "matlab_agent",
        config_file,
        substitute_func=lambda config: {"hooked": config["root"]["value"]},
    )
    assert loaded == {"hooked": 1}


def test_load_config_default_template_not_found() -> None:
    """Missing default package template should raise FileNotFoundError."""
    with patch("importlib.resources.open_text") as mock_open_text:
        mock_open_text.side_effect = FileNotFoundError()
        with pytest.raises(FileNotFoundError):
            load_config("matlab_agent")


def test_load_config_yaml_error(tmp_path: Path) -> None:
    """YAML parser errors should propagate."""
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("invalid: yaml: ::::", encoding="utf-8")
    with patch("yaml.safe_load") as mock_safe_load:
        mock_safe_load.side_effect = yaml.YAMLError("bad yaml")
        with pytest.raises(yaml.YAMLError):
            load_config("matlab_agent", config_file)


def test_substitute_env_vars_with_defaults() -> None:
    """Placeholder substitution should use env values or defaults."""
    os.environ.pop("CFG_A", None)
    os.environ["CFG_B"] = "set"
    result = substitute_env_vars(
        {
            "a": "${CFG_A:default}",
            "b": "${CFG_B}",
            "nested": ["${CFG_A:inner}", "${CFG_B}"],
        }
    )
    os.environ.pop("CFG_B", None)
    assert result["a"] == "default"
    assert result["b"] == "set"
    assert result["nested"] == ["inner", "set"]


def test_get_config_value_nested() -> None:
    """Dotted-path lookup should return nested values and defaults."""
    config = {"root": {"leaf": 7}}
    assert get_config_value(config, "root.leaf") == 7
    assert get_config_value(config, "root.missing", default="x") == "x"


def test_get_base_dir_defaults_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Base dir helper should fallback to cwd when no project markers exist."""
    monkeypatch.setattr(Path, "exists", lambda _self: False)
    monkeypatch.setattr(Path, "cwd", classmethod(lambda _cls: tmp_path))
    assert get_base_dir() == tmp_path
