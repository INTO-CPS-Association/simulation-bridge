"""
Configuration manager for the MATLAB Agent using Pydantic for validation.
"""

from pathlib import Path
from typing import Optional, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field, ValidationError, ConfigDict

from .logger import get_logger
from .config_loader import load_config

logger = get_logger()


class LogLevel(str, Enum):
    """Supported logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Config(BaseModel):
    """Main configuration model using Pydantic for validation."""
    model_config = ConfigDict(extra='ignore')

    # Agent configuration
    agent_id: str = Field(default="matlab")

    # RabbitMQ configuration
    rabbitmq_host: str = Field(default="localhost")
    rabbitmq_port: int = Field(default=5672)
    rabbitmq_username: str = Field(default="guest")
    rabbitmq_password: str = Field(default="guest")
    rabbitmq_heartbeat: int = Field(default=600)
    rabbitmq_virtual_host: str = Field(default="/")

    # Exchanges configuration
    input_exchange: str = Field(default="ex.bridge.output")
    output_exchange: str = Field(default="ex.sim.result")

    # Queue configuration
    queue_durable: bool = Field(default=True)
    queue_prefetch_count: int = Field(default=1)

    # Logging configuration
    log_level: LogLevel = Field(default=LogLevel.INFO)
    log_file: str = Field(default="logs/matlab_agent.log")

    # TCP configuration
    tcp_host: str = Field(default="localhost")
    tcp_port: int = Field(default=5678)

    # Simulation configuration
    simulation_type: str = Field(default="batch")

    # Response templates
    # Success template
    success_status: Literal["success"] = Field(default="success")
    success_timestamp_format: str = Field(default="%Y-%m-%dT%H:%M:%SZ")
    success_include_metadata: bool = Field(default=True)
    success_metadata_fields: list[str] = Field(
        default=["execution_time", "memory_usage", "matlab_version"]
    )

    # Error template
    error_status: Literal["error"] = Field(default="error")
    error_include_stacktrace: bool = Field(default=False)
    error_timestamp_format: str = Field(default="%Y-%m-%dT%H:%M:%SZ")
    error_codes: Dict[str, int] = Field(
        default={
            "invalid_config": 400,
            "matlab_start_failure": 500,
            "execution_error": 500,
            "timeout": 504,
            "missing_file": 404
        }
    )

    # Progress template
    progress_status: Literal["in_progress"] = Field(default="in_progress")
    progress_include_percentage: bool = Field(default=True)
    progress_update_interval: int = Field(default=5)
    progress_timestamp_format: str = Field(default="%Y-%m-%dT%H:%M:%SZ")

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary with nested structure."""
        return {
            "agent": {
                "agent_id": self.agent_id
            },
            "rabbitmq": {
                "host": self.rabbitmq_host,
                "port": self.rabbitmq_port,
                "username": self.rabbitmq_username,
                "password": self.rabbitmq_password,
                "heartbeat": self.rabbitmq_heartbeat,
                "vhost": self.rabbitmq_virtual_host
            },
            "exchanges": {
                "input": self.input_exchange,
                "output": self.output_exchange
            },
            "queue": {
                "durable": self.queue_durable,
                "prefetch_count": self.queue_prefetch_count
            },
            "logging": {
                "level": self.log_level.value,
                "file": self.log_file
            },
            "tcp": {
                "host": self.tcp_host,
                "port": self.tcp_port
            },
            "response_templates": {
                "success": {
                    "status": self.success_status,
                    "simulation": {
                        "type": self.simulation_type
                    },
                    "timestamp_format": self.success_timestamp_format,
                    "include_metadata": self.success_include_metadata,
                    "metadata_fields": self.success_metadata_fields
                },
                "error": {
                    "status": self.error_status,
                    "include_stacktrace": self.error_include_stacktrace,
                    "error_codes": self.error_codes,
                    "timestamp_format": self.error_timestamp_format
                },
                "progress": {
                    "status": self.progress_status,
                    "include_percentage": self.progress_include_percentage,
                    "update_interval": self.progress_update_interval,
                    "timestamp_format": self.progress_timestamp_format
                }
            }
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'Config':
        """Create a Config instance from a nested dictionary."""
        # Extract values from nested structure
        flat_config = {}

        # Extract agent section if present
        if agent := config_dict.get("agent", {}):
            flat_config["agent_id"] = agent.get("agent_id", "matlab")

        # Extract rabbitmq section if present
        if rabbitmq := config_dict.get("rabbitmq", {}):
            flat_config["rabbitmq_host"] = rabbitmq.get("host", "localhost")
            flat_config["rabbitmq_port"] = rabbitmq.get("port", 5672)
            flat_config["rabbitmq_username"] = rabbitmq.get(
                "username", "guest")
            flat_config["rabbitmq_password"] = rabbitmq.get(
                "password", "guest")
            flat_config["rabbitmq_heartbeat"] = rabbitmq.get("heartbeat", 600)
            flat_config["rabbitmq_virtual_host"] = rabbitmq.get(
                "vhost", "/")

        # Extract exchanges section if present
        if exchanges := config_dict.get("exchanges", {}):
            flat_config["input_exchange"] = exchanges.get(
                "input", "ex.bridge.output")
            flat_config["output_exchange"] = exchanges.get(
                "output", "ex.sim.result")

        # Extract queue section if present
        if queue := config_dict.get("queue", {}):
            flat_config["queue_durable"] = queue.get("durable", True)
            flat_config["queue_prefetch_count"] = queue.get(
                "prefetch_count", 1)

        # Extract logging section if present
        if logging := config_dict.get("logging", {}):
            flat_config["log_level"] = logging.get("level", LogLevel.INFO)
            flat_config["log_file"] = logging.get(
                "file", "logs/matlab_agent.log")

        # Extract tcp section if present
        if tcp := config_dict.get("tcp", {}):
            flat_config["tcp_host"] = tcp.get("host", "localhost")
            flat_config["tcp_port"] = tcp.get("port", 5678)

        # Extract response_templates section if present
        if templates := config_dict.get("response_templates", {}):
            # Success template
            if success := templates.get("success", {}):
                flat_config["success_status"] = success.get(
                    "status", "success")
                if simulation := success.get("simulation", {}):
                    flat_config["simulation_type"] = simulation.get(
                        "type", "batch")
                flat_config["success_timestamp_format"] = success.get(
                    "timestamp_format", "%Y-%m-%dT%H:%M:%SZ")
                flat_config["success_include_metadata"] = success.get(
                    "include_metadata", True)
                flat_config["success_metadata_fields"] = success.get("metadata_fields",
                                                                     ["execution_time",
                                                                      "memory_usage",
                                                                      "matlab_version"])

            # Error template
            if error := templates.get("error", {}):
                flat_config["error_status"] = error.get("status", "error")
                flat_config["error_include_stacktrace"] = error.get(
                    "include_stacktrace", False)
                flat_config["error_timestamp_format"] = error.get(
                    "timestamp_format", "%Y-%m-%dT%H:%M:%SZ")
                flat_config["error_codes"] = error.get("error_codes", {
                    "invalid_config": 400,
                    "matlab_start_failure": 500,
                    "execution_error": 500,
                    "timeout": 504,
                    "missing_file": 404
                })

            # Progress template
            if progress := templates.get("progress", {}):
                flat_config["progress_status"] = progress.get(
                    "status", "in_progress")
                flat_config["progress_include_percentage"] = progress.get(
                    "include_percentage", True)
                flat_config["progress_update_interval"] = progress.get(
                    "update_interval", 5)
                flat_config["progress_timestamp_format"] = progress.get(
                    "timestamp_format", "%Y-%m-%dT%H:%M:%SZ")

        return cls(**flat_config)


class ConfigManager:
    """
    Manager for loading and providing access to application configuration.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Initialize the configuration manager.

        Args:
            config_path (Optional[str]): Path to the configuration file.
                                         If None, uses the default location.
        """
        self.config_path: Path = Path(config_path) if config_path else Path(
            __file__).parent.parent.parent / "config" / "config.yaml"
        try:
            raw_config = load_config(self.config_path)
            self.config = self._validate_config(raw_config)
        except (FileNotFoundError, ValidationError) as e:
            logger.warning("Configuration error: %s, using defaults.", str(e))
            self.config = self.get_default_config()
        except (IOError, PermissionError) as e:
            logger.error("File access error: %s, using defaults.", str(e))
            self.config = self.get_default_config()
        except Exception as e:
            logger.error("Unexpected error: %s, using defaults.", str(e))
            logger.exception("Full traceback:")
            self.config = self.get_default_config()

    def _validate_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration using Pydantic model."""
        try:
            # Create Config instance from nested dictionary
            config_instance = Config.from_dict(config_data)
            # Convert back to nested dictionary format
            validated_config = config_instance.to_dict()
            logger.info("Configuration validated successfully.")
            return validated_config
        except ValidationError as e:
            logger.error("Configuration validation failed: %s", str(e))
            raise

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration as dictionary."""
        return Config().to_dict()

    def get_config(self) -> Dict[str, Any]:
        """
        Get the loaded configuration.

        Returns:
            Dict[str, Any]: Configuration parameters
        """
        return self.config
