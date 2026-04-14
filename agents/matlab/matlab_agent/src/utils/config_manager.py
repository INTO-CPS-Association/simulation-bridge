"""Configuration manager for the MATLAB agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from base_agent.utils.config_loader import load_config
from base_agent.utils.config_manager import (
    BaseConfigManager,
    LogLevel,
    build_common_config,
    flatten_common_config,
)
from base_agent.utils.logger import get_logger

from .constants import DEFAULT_INPUT_PORT, DEFAULT_OUTPUT_HOST, DEFAULT_OUTPUT_PORT

logger = get_logger("MATLAB-AGENT")


class Config(BaseModel):
    """MATLAB configuration model using Pydantic validation."""

    model_config = ConfigDict(extra="ignore")

    # Agent configuration
    agent_id: str = Field(default="matlab")

    # RabbitMQ configuration
    rabbitmq_host: str = Field(default="localhost")
    rabbitmq_port: int = Field(default=5672)
    rabbitmq_username: str = Field(default="guest")
    rabbitmq_password: str = Field(default="guest")
    rabbitmq_heartbeat: int = Field(default=600)
    rabbitmq_virtual_host: str = Field(default="/")
    rabbitmq_tls: bool = Field(default=False)

    # Simulation folder path
    simulation_path: str = Field(default=".")

    # Exchanges configuration
    input_exchange: str = Field(default="ex.bridge.output")
    output_exchange: str = Field(default="ex.sim.result")

    # Queue configuration
    queue_durable: bool = Field(default=True)
    queue_prefetch_count: int = Field(default=1)

    # Logging configuration
    log_level: LogLevel = Field(default=LogLevel.INFO)
    log_file: str = Field(default="logs/matlab_agent.log")

    # Performance configuration
    performance_enabled: bool = Field(default=False)
    performance_log_dir: str = Field(default="performance_logs")
    performance_log_filename: str = Field(default="performance_metrics.csv")

    # TCP configuration
    tcp_host: str = Field(default=DEFAULT_OUTPUT_HOST)
    tcp_input_port: int = Field(default=DEFAULT_INPUT_PORT)
    tcp_output_port: int = Field(default=DEFAULT_OUTPUT_PORT)

    # Response templates
    success_status: Literal["success"] = Field(default="success")
    simulation_type: Literal["batch", "streaming"] = Field(default="batch")
    success_timestamp_format: str = Field(default="%Y-%m-%dT%H:%M:%SZ")
    success_include_metadata: bool = Field(default=True)
    success_metadata_fields: list[str] = Field(
        default_factory=lambda: ["execution_time", "memory_usage", "matlab_version"]
    )

    error_status: Literal["error"] = Field(default="error")
    error_include_stacktrace: bool = Field(default=False)
    error_timestamp_format: str = Field(default="%Y-%m-%dT%H:%M:%SZ")
    error_codes: Dict[str, int] = Field(
        default_factory=lambda: {
            "invalid_config": 400,
            "matlab_start_failure": 500,
            "execution_error": 500,
            "timeout": 504,
            "missing_file": 404,
        }
    )

    progress_status: Literal["in_progress"] = Field(default="in_progress")
    progress_include_percentage: bool = Field(default=True)
    progress_update_interval: int = Field(default=5)
    progress_timestamp_format: str = Field(default="%Y-%m-%dT%H:%M:%SZ")

    def _common_flat_config(self) -> Dict[str, Any]:
        """Return shared flat configuration keys used by base helpers."""

        log_level = getattr(self.log_level, "value", self.log_level)
        return {
            "agent_id": self.agent_id,
            "rabbitmq_host": self.rabbitmq_host,
            "rabbitmq_port": self.rabbitmq_port,
            "rabbitmq_username": self.rabbitmq_username,
            "rabbitmq_password": self.rabbitmq_password,
            "rabbitmq_heartbeat": self.rabbitmq_heartbeat,
            "rabbitmq_virtual_host": self.rabbitmq_virtual_host,
            "rabbitmq_tls": self.rabbitmq_tls,
            "simulation_path": self.simulation_path,
            "input_exchange": self.input_exchange,
            "output_exchange": self.output_exchange,
            "queue_durable": self.queue_durable,
            "queue_prefetch_count": self.queue_prefetch_count,
            "log_level": log_level,
            "log_file": self.log_file,
            "performance_enabled": self.performance_enabled,
            "performance_log_dir": self.performance_log_dir,
            "performance_log_filename": self.performance_log_filename,
            "success_status": self.success_status,
            "simulation_type": self.simulation_type,
            "success_timestamp_format": self.success_timestamp_format,
            "success_include_metadata": self.success_include_metadata,
            "success_metadata_fields": self.success_metadata_fields,
            "error_status": self.error_status,
            "error_include_stacktrace": self.error_include_stacktrace,
            "error_timestamp_format": self.error_timestamp_format,
            "error_codes": self.error_codes,
            "progress_status": self.progress_status,
            "progress_include_percentage": self.progress_include_percentage,
            "progress_update_interval": self.progress_update_interval,
            "progress_timestamp_format": self.progress_timestamp_format,
        }

    @classmethod
    def _default_flat_config(cls) -> Dict[str, Any]:
        """Return shared defaults as a flat dictionary."""

        defaults = cls()
        return {
            "agent_id": defaults.agent_id,
            "rabbitmq_host": defaults.rabbitmq_host,
            "rabbitmq_port": defaults.rabbitmq_port,
            "rabbitmq_username": defaults.rabbitmq_username,
            "rabbitmq_password": defaults.rabbitmq_password,
            "rabbitmq_heartbeat": defaults.rabbitmq_heartbeat,
            "rabbitmq_virtual_host": defaults.rabbitmq_virtual_host,
            "rabbitmq_tls": defaults.rabbitmq_tls,
            "simulation_path": defaults.simulation_path,
            "input_exchange": defaults.input_exchange,
            "output_exchange": defaults.output_exchange,
            "queue_durable": defaults.queue_durable,
            "queue_prefetch_count": defaults.queue_prefetch_count,
            "log_level": defaults.log_level,
            "log_file": defaults.log_file,
            "performance_enabled": defaults.performance_enabled,
            "performance_log_dir": defaults.performance_log_dir,
            "performance_log_filename": defaults.performance_log_filename,
            "success_status": defaults.success_status,
            "simulation_type": defaults.simulation_type,
            "success_timestamp_format": defaults.success_timestamp_format,
            "success_include_metadata": defaults.success_include_metadata,
            "success_metadata_fields": defaults.success_metadata_fields,
            "error_status": defaults.error_status,
            "error_include_stacktrace": defaults.error_include_stacktrace,
            "error_timestamp_format": defaults.error_timestamp_format,
            "error_codes": defaults.error_codes,
            "progress_status": defaults.progress_status,
            "progress_include_percentage": defaults.progress_include_percentage,
            "progress_update_interval": defaults.progress_update_interval,
            "progress_timestamp_format": defaults.progress_timestamp_format,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize model to nested runtime configuration format."""

        config = build_common_config(self._common_flat_config())
        config["tcp"] = {
            "host": self.tcp_host,
            "input_port": self.tcp_input_port,
            "output_port": self.tcp_output_port,
        }
        return config

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "Config":
        """Create validated model from nested runtime configuration."""

        flat_config = flatten_common_config(config_dict, cls._default_flat_config())

        defaults = cls()
        if tcp := config_dict.get("tcp", {}):
            flat_config["tcp_host"] = tcp.get("host", defaults.tcp_host)
            flat_config["tcp_input_port"] = tcp.get(
                "input_port",
                defaults.tcp_input_port,
            )
            flat_config["tcp_output_port"] = tcp.get(
                "output_port",
                defaults.tcp_output_port,
            )

        return cls(**flat_config)


class ConfigManager(BaseConfigManager):
    """MATLAB configuration manager backed by shared base manager logic."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        default_path = Path(__file__).parent.parent.parent.parent / "config.yaml"
        super().__init__(
            package_name="matlab_agent",
            validate_config_func=self._validate_with_model,
            default_config_func=self._default_config,
            validation_errors=(ValidationError,),
            logger=logger,
            config_path=config_path,
            default_config_path=default_path,
            load_config_func=load_config,
        )

    @staticmethod
    def _validate_with_model(config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate config data via the MATLAB Pydantic model."""

        try:
            config_instance = Config.from_dict(config_data)
            return config_instance.to_dict()
        except ValidationError as error:
            logger.error("Configuration validation failed: %s", str(error))
            raise

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """Build default nested config."""

        return Config().to_dict()


__all__ = ["Config", "ConfigManager", "LogLevel"]
