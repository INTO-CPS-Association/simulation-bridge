"""Test suite for the ConfigManager class.

This refactored version removes duplicated configuration stubs by introducing a
single reusable ``base_config`` fixture.  Where individual tests need to tweak
values, they operate on a ``deepcopy`` so that the canonical fixture remains
pristine for all subsequent tests.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest
from pydantic import ValidationError

from src.utils.config_manager import ConfigManager


@pytest.fixture(scope="module")
def base_config(dummy_credentials: dict) -> dict:
    """Return a fully‑populated configuration template shared by all tests."""

    rabbit_creds: dict = dummy_credentials.get("rabbitmq", {})
    return {
        "agent": {"agent_id": "matlab"},
        "rabbitmq": {
            "host": "localhost",
            "port": 5672,
            "username": rabbit_creds.get("username", "guest"),
            "password": rabbit_creds.get("password", "guest"),
            "heartbeat": 600,
        },
        "exchanges": {
            "input": "ex.bridge.output",
            "output": "ex.sim.result",
        },
        "queue": {
            "durable": True,
            "prefetch_count": 1,
        },
        "logging": {
            "level": "INFO",
            "file": "logs/matlab_agent.log",
        },
        "tcp": {
            "host": "localhost",
            "port": 5678,
        },
        "response_templates": {
            "success": {
                "status": "success",
                "simulation": {"type": "batch"},
                "timestamp_format": "%Y-%m-%dT%H:%M:%SZ",
                "include_metadata": True,
                "metadata_fields": [
                    "execution_time",
                    "memory_usage",
                    "matlab_version",
                ],
            },
            "error": {
                "status": "error",
                "include_stacktrace": False,
                "error_codes": {
                    "invalid_config": 400,
                    "matlab_start_failure": 500,
                    "execution_error": 500,
                    "timeout": 504,
                    "missing_file": 404,
                },
                "timestamp_format": "%Y-%m-%dT%H:%M:%SZ",
            },
            "progress": {
                "status": "in_progress",
                "include_percentage": True,
                "update_interval": 5,
                "timestamp_format": "%Y-%m-%dT%H:%M:%SZ",
            },
        },
    }


@pytest.fixture
def config_path() -> Path:
    """Fake configuration path used throughout the tests."""

    return Path("/fake/path/config.yaml")


@pytest.fixture
def patched_load(base_config: dict):
    """Patch the ``load_config`` helper used by :class:`ConfigManager`."""

    with mock.patch(
        "src.utils.config_manager.load_config", return_value=deepcopy(base_config)
    ) as mocked:
        yield mocked


@pytest.fixture
def patched_exists():
    """Pretend that any ``Path.exists`` call returns *True*."""

    with mock.patch.object(Path, "exists", return_value=True):
        yield


@pytest.fixture
def manager(config_path: Path, patched_load, patched_exists):
    """A :class:`ConfigManager` instance pre‑loaded with *base_config*."""

    return ConfigManager(config_path)


def test_manager_initialization(
        manager: ConfigManager, patched_load, config_path):
    """The manager should forward *config_path* to ``load_config`` exactly once."""

    patched_load.assert_called_once_with(Path(config_path))
    assert manager.config["agent"]["agent_id"] == "matlab"


def test_get_default_config():
    """The factory default configuration is stable and complete."""

    cm = ConfigManager()
    default_cfg = cm.get_default_config()

    assert default_cfg["agent"]["agent_id"] == "matlab"
    assert default_cfg["rabbitmq"]["port"] == 5672


def test_get_config(manager: ConfigManager):
    """``get_config`` should return the same data originally loaded."""

    assert manager.get_config()["rabbitmq"]["host"] == "localhost"


@pytest.mark.parametrize("agent_id", ["matlab", "python_sim"])
def test_validate_config_success(agent_id: str, base_config: dict):
    """Any valid configuration variant should pass model validation."""

    cfg = deepcopy(base_config)
    cfg["agent"]["agent_id"] = agent_id

    validated = ConfigManager()._validate_config(
        cfg)  # pylint: disable=protected-access
    assert validated["agent"]["agent_id"] == agent_id


def test_validate_config_failure():
    """An invalid configuration must raise a :class:`ValidationError`."""

    with pytest.raises(ValidationError):
        ConfigManager()._validate_config({"rabbitmq": {"port": "not_a_number"}})


def test_initialization_with_invalid_path(monkeypatch):
    """If the file is missing, the manager should fall back to defaults."""

    monkeypatch.setattr(Path, "exists", lambda *_: False)

    cm = ConfigManager("/invalid/path/config.yaml")

    assert cm.config == cm.get_default_config()
