"""Shared configuration helpers and manager utilities for simulator agents."""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from base_agent.interfaces.config_manager import IConfigManager

from .config_loader import load_config
from .logger import get_logger


class LogLevel(str, Enum):
    """Supported logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def flatten_common_config(
    config_dict: Dict[str, Any],
    defaults: Dict[str, Any],
) -> Dict[str, Any]:
    """Flatten shared nested config sections into a single-level dictionary."""

    flat_config: Dict[str, Any] = {}

    if agent := config_dict.get("agent", {}):
        flat_config["agent_id"] = agent.get("agent_id", defaults["agent_id"])

    if rabbitmq := config_dict.get("rabbitmq", {}):
        flat_config["rabbitmq_host"] = rabbitmq.get("host", defaults["rabbitmq_host"])
        flat_config["rabbitmq_port"] = rabbitmq.get("port", defaults["rabbitmq_port"])
        flat_config["rabbitmq_username"] = rabbitmq.get(
            "username",
            defaults["rabbitmq_username"],
        )
        flat_config["rabbitmq_password"] = rabbitmq.get(
            "password",
            defaults["rabbitmq_password"],
        )
        flat_config["rabbitmq_heartbeat"] = rabbitmq.get(
            "heartbeat",
            defaults["rabbitmq_heartbeat"],
        )
        flat_config["rabbitmq_virtual_host"] = rabbitmq.get(
            "vhost",
            defaults["rabbitmq_virtual_host"],
        )
        flat_config["rabbitmq_tls"] = rabbitmq.get("tls", defaults["rabbitmq_tls"])

    if simulation := config_dict.get("simulation", {}):
        flat_config["simulation_path"] = simulation.get("path", defaults["simulation_path"])

    if exchanges := config_dict.get("exchanges", {}):
        flat_config["input_exchange"] = exchanges.get("input", defaults["input_exchange"])
        flat_config["output_exchange"] = exchanges.get(
            "output",
            defaults["output_exchange"],
        )

    if queue := config_dict.get("queue", {}):
        flat_config["queue_durable"] = queue.get("durable", defaults["queue_durable"])
        flat_config["queue_prefetch_count"] = queue.get(
            "prefetch_count",
            defaults["queue_prefetch_count"],
        )

    if logging_cfg := config_dict.get("logging", {}):
        flat_config["log_level"] = logging_cfg.get("level", defaults["log_level"])
        flat_config["log_file"] = logging_cfg.get("file", defaults["log_file"])

    if performance := config_dict.get("performance", {}):
        flat_config["performance_enabled"] = performance.get(
            "enabled",
            defaults["performance_enabled"],
        )
        flat_config["performance_log_dir"] = performance.get(
            "log_dir",
            defaults["performance_log_dir"],
        )
        flat_config["performance_log_filename"] = performance.get(
            "log_filename",
            defaults["performance_log_filename"],
        )

    if templates := config_dict.get("response_templates", {}):
        if success := templates.get("success", {}):
            flat_config["success_status"] = success.get("status", defaults["success_status"])
            if simulation_cfg := success.get("simulation", {}):
                flat_config["simulation_type"] = simulation_cfg.get(
                    "type",
                    defaults["simulation_type"],
                )
            flat_config["success_timestamp_format"] = success.get(
                "timestamp_format",
                defaults["success_timestamp_format"],
            )
            flat_config["success_include_metadata"] = success.get(
                "include_metadata",
                defaults["success_include_metadata"],
            )
            flat_config["success_metadata_fields"] = success.get(
                "metadata_fields",
                deepcopy(defaults["success_metadata_fields"]),
            )

        if error := templates.get("error", {}):
            flat_config["error_status"] = error.get("status", defaults["error_status"])
            flat_config["error_include_stacktrace"] = error.get(
                "include_stacktrace",
                defaults["error_include_stacktrace"],
            )
            flat_config["error_timestamp_format"] = error.get(
                "timestamp_format",
                defaults["error_timestamp_format"],
            )
            flat_config["error_codes"] = error.get(
                "error_codes",
                deepcopy(defaults["error_codes"]),
            )

        if progress := templates.get("progress", {}):
            flat_config["progress_status"] = progress.get(
                "status",
                defaults["progress_status"],
            )
            flat_config["progress_include_percentage"] = progress.get(
                "include_percentage",
                defaults["progress_include_percentage"],
            )
            flat_config["progress_update_interval"] = progress.get(
                "update_interval",
                defaults["progress_update_interval"],
            )
            flat_config["progress_timestamp_format"] = progress.get(
                "timestamp_format",
                defaults["progress_timestamp_format"],
            )

    return flat_config


def build_common_config(flat_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build shared nested config sections from a flattened dictionary."""

    return {
        "agent": {
            "agent_id": flat_config["agent_id"],
        },
        "rabbitmq": {
            "host": flat_config["rabbitmq_host"],
            "port": flat_config["rabbitmq_port"],
            "username": flat_config["rabbitmq_username"],
            "password": flat_config["rabbitmq_password"],
            "heartbeat": flat_config["rabbitmq_heartbeat"],
            "vhost": flat_config["rabbitmq_virtual_host"],
            "tls": flat_config["rabbitmq_tls"],
        },
        "simulation": {
            "path": flat_config["simulation_path"],
        },
        "exchanges": {
            "input": flat_config["input_exchange"],
            "output": flat_config["output_exchange"],
        },
        "queue": {
            "durable": flat_config["queue_durable"],
            "prefetch_count": flat_config["queue_prefetch_count"],
        },
        "logging": {
            "level": flat_config["log_level"],
            "file": flat_config["log_file"],
        },
        "performance": {
            "enabled": flat_config["performance_enabled"],
            "log_dir": flat_config["performance_log_dir"],
            "log_filename": flat_config["performance_log_filename"],
        },
        "response_templates": {
            "success": {
                "status": flat_config["success_status"],
                "simulation": {
                    "type": flat_config["simulation_type"],
                },
                "timestamp_format": flat_config["success_timestamp_format"],
                "include_metadata": flat_config["success_include_metadata"],
                "metadata_fields": flat_config["success_metadata_fields"],
            },
            "error": {
                "status": flat_config["error_status"],
                "include_stacktrace": flat_config["error_include_stacktrace"],
                "error_codes": flat_config["error_codes"],
                "timestamp_format": flat_config["error_timestamp_format"],
            },
            "progress": {
                "status": flat_config["progress_status"],
                "include_percentage": flat_config["progress_include_percentage"],
                "update_interval": flat_config["progress_update_interval"],
                "timestamp_format": flat_config["progress_timestamp_format"],
            },
        },
    }


class BaseConfigManager(IConfigManager):  # pylint: disable=too-many-instance-attributes
    """Reusable config manager that delegates validation/defaults to callables."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        package_name: str,
        validate_config_func: Callable[[Dict[str, Any]], Dict[str, Any]],
        default_config_func: Callable[[], Dict[str, Any]],
        validation_errors: tuple[type[Exception], ...] = (),
        logger: Optional[logging.Logger] = None,
        config_path: Optional[str] = None,
        default_config_path: Optional[Path] = None,
        load_config_func: Callable[..., Dict[str, Any]] = load_config,
    ) -> None:
        self._package_name = package_name
        self._validate_config_func = validate_config_func
        self._default_config_func = default_config_func
        self._validation_errors = validation_errors
        self._logger = logger or get_logger("AGENT")
        self._load_config = load_config_func
        self.config_path: Path = Path(config_path) if config_path else (
            default_config_path or Path("config.yaml")
        )

        config_errors = (FileNotFoundError,) + self._validation_errors
        try:
            raw_config = self._load_config(
                package_name=self._package_name,
                config_path=self.config_path,
            )
            self.config = self._validate_config(raw_config)
        except config_errors as error:
            self._logger.warning("Configuration error: %s, using defaults.", str(error))
            self.config = self.get_default_config()
        except (IOError, PermissionError) as error:
            self._logger.error("File access error: %s, using defaults.", str(error))
            self.config = self.get_default_config()
        except Exception as error:  # pylint: disable=broad-exception-caught
            self._logger.error("Unexpected error: %s, using defaults.", str(error))
            self._logger.exception("Full traceback:")
            self.config = self.get_default_config()

    def _validate_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate incoming configuration with the injected validator."""

        validated_config = self._validate_config_func(config_data)
        self._logger.info("Configuration validated successfully.")
        return validated_config

    def get_default_config(self) -> Dict[str, Any]:
        """Return default config via injected default factory."""

        return self._default_config_func()

    def get_config(self) -> Dict[str, Any]:
        """Return current validated configuration."""

        return self.config


__all__ = [
    "BaseConfigManager",
    "LogLevel",
    "build_common_config",
    "flatten_common_config",
]
