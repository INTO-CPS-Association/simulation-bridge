"""Tests for shared config manager helpers and manager abstraction."""

from pathlib import Path
from unittest import mock

import pytest

from base_agent.utils.config_manager import (
    BaseConfigManager,
    build_common_config,
    flatten_common_config,
)
from base_agent.utils.logger import get_logger


def _defaults():
    return {
        "agent_id": "dummy",
        "rabbitmq_host": "localhost",
        "rabbitmq_port": 5672,
        "rabbitmq_username": "guest",
        "rabbitmq_password": "guest",
        "rabbitmq_heartbeat": 600,
        "rabbitmq_virtual_host": "/",
        "rabbitmq_tls": False,
        "simulation_path": ".",
        "input_exchange": "ex.bridge.output",
        "output_exchange": "ex.sim.result",
        "queue_durable": True,
        "queue_prefetch_count": 1,
        "log_level": "INFO",
        "log_file": "logs/dummy_agent.log",
        "performance_enabled": False,
        "performance_log_dir": "performance_logs",
        "performance_log_filename": "performance_metrics.csv",
        "success_status": "success",
        "simulation_type": "batch",
        "success_timestamp_format": "%Y-%m-%dT%H:%M:%SZ",
        "success_include_metadata": True,
        "success_metadata_fields": ["execution_time", "memory_usage", "dummy_version"],
        "error_status": "error",
        "error_include_stacktrace": False,
        "error_timestamp_format": "%Y-%m-%dT%H:%M:%SZ",
        "error_codes": {"invalid_config": 400},
        "progress_status": "in_progress",
        "progress_include_percentage": True,
        "progress_update_interval": 5,
        "progress_timestamp_format": "%Y-%m-%dT%H:%M:%SZ",
    }


def test_flatten_common_config_reads_nested_sections():
    """Shared flatten helper should read known nested keys."""

    nested = {
        "agent": {"agent_id": "configured-dummy"},
        "rabbitmq": {"port": 5673},
        "logging": {"level": "DEBUG"},
        "response_templates": {
            "success": {"metadata_fields": ["execution_time"]},
            "error": {"error_codes": {"invalid_config": 422}},
        },
    }

    flat = flatten_common_config(nested, _defaults())

    assert flat["agent_id"] == "configured-dummy"
    assert flat["rabbitmq_port"] == 5673
    assert flat["log_level"] == "DEBUG"
    assert flat["success_metadata_fields"] == ["execution_time"]
    assert flat["error_codes"] == {"invalid_config": 422}


def test_build_common_config_creates_nested_structure():
    """Shared build helper should return runtime nested sections."""

    nested = build_common_config(_defaults())

    assert nested["agent"]["agent_id"] == "dummy"
    assert nested["rabbitmq"]["port"] == 5672
    assert nested["logging"]["level"] == "INFO"
    assert nested["response_templates"]["success"]["simulation"]["type"] == "batch"


def test_base_config_manager_uses_injected_loader_and_validator():
    """Base manager should load config and validate via injected callback."""

    loader = mock.Mock(return_value={"agent": {"agent_id": "worker"}})
    validator = mock.Mock(return_value={"agent": {"agent_id": "validated"}})
    default_factory = mock.Mock(return_value={"agent": {"agent_id": "default"}})

    manager = BaseConfigManager(
        package_name="dummy_agent",
        validate_config_func=validator,
        default_config_func=default_factory,
        validation_errors=(ValueError,),
        logger=get_logger("BASE-DUMMY"),
        config_path="config/custom.yaml",
        default_config_path=Path("unused.yaml"),
        load_config_func=loader,
    )

    loader.assert_called_once_with(
        package_name="dummy_agent",
        config_path=Path("config/custom.yaml"),
    )
    validator.assert_called_once_with({"agent": {"agent_id": "worker"}})
    assert manager.get_config()["agent"]["agent_id"] == "validated"
    default_factory.assert_not_called()


def test_base_config_manager_falls_back_to_defaults_on_validation_error():
    """Validation errors should trigger warning path and default config fallback."""

    loader = mock.Mock(return_value={"invalid": True})
    validator = mock.Mock(side_effect=ValueError("bad config"))
    default_factory = mock.Mock(return_value={"agent": {"agent_id": "default"}})

    manager = BaseConfigManager(
        package_name="dummy_agent",
        validate_config_func=validator,
        default_config_func=default_factory,
        validation_errors=(ValueError,),
        logger=get_logger("BASE-DUMMY"),
        load_config_func=loader,
    )

    assert manager.get_config()["agent"]["agent_id"] == "default"
    default_factory.assert_called_once()


def test_base_config_manager_validation_raises_when_called_directly():
    """Calling _validate_config directly should propagate validator exceptions."""

    manager = BaseConfigManager(
        package_name="dummy_agent",
        validate_config_func=lambda data: data,
        default_config_func=lambda: {},
        logger=get_logger("BASE-DUMMY"),
        load_config_func=lambda **_kwargs: {},
    )

    manager._validate_config_func = mock.Mock(side_effect=RuntimeError("boom"))  # pylint: disable=protected-access
    with pytest.raises(RuntimeError):
        manager._validate_config({})
