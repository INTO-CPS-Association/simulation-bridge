"""
config_manager.py - Configuration manager utility

This module provides functionality to load and manage application configuration
using Pydantic models for validation and nested structure.
"""
import yaml
from typing import Optional, Dict, Any, Literal, List
from pathlib import Path
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


class ExchangeConfig(BaseModel):
    """Configuration for RabbitMQ exchanges."""
    name: str
    type: str
    durable: bool
    auto_delete: bool
    internal: bool


class QueueConfig(BaseModel):
    """Configuration for RabbitMQ queues."""
    name: str
    durable: bool
    exclusive: bool
    auto_delete: bool


class BindingConfig(BaseModel):
    """Configuration for RabbitMQ bindings."""
    queue: str
    exchange: str
    routing_key: str


class RabbitMQInfrastructure(BaseModel):
    """Configuration for RabbitMQ infrastructure."""
    exchanges: List[ExchangeConfig]
    queues: List[QueueConfig]
    bindings: List[BindingConfig]


class RabbitMQConfig(BaseModel):
    """Configuration for RabbitMQ connection."""
    host: str
    port: int
    virtual_host: str
    infrastructure: RabbitMQInfrastructure


class MQTTConfig(BaseModel):
    """Configuration for MQTT connection."""
    host: str
    port: int
    keepalive: int
    input_topic: str
    output_topic: str
    qos: int


class RESTConfig(BaseModel):
    """Configuration for REST API."""
    host: str
    port: int
    input_endpoint: str
    debug: bool
    client: dict[str, str | int]  # This will contain host, port, base_url, and output_endpoint


class LoggingConfig(BaseModel):
    """Configuration for logging."""
    level: LogLevel
    format: str
    file: str


class SimulationBridgeConfig(BaseModel):
    """Configuration for simulation bridge."""
    bridge_id: str


class Config(BaseModel):
    """Main configuration model using Pydantic for validation."""
    model_config = ConfigDict(extra='ignore')

    simulation_bridge: SimulationBridgeConfig
    rabbitmq: RabbitMQConfig
    mqtt: MQTTConfig
    rest: RESTConfig
    logging: LoggingConfig

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary with nested structure."""
        return {
            'simulation_bridge': self.simulation_bridge.model_dump(),
            'rabbitmq': self.rabbitmq.model_dump(),
            'mqtt': self.mqtt.model_dump(),
            'rest': self.rest.model_dump(),
            'logging': self.logging.model_dump()
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'Config':
        """Create a Config instance from a nested dictionary."""
        return cls(**config_dict)


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
            __file__).parent.parent.parent.parent / "config.yaml"
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
        return Config(
            simulation_bridge=SimulationBridgeConfig(bridge_id="simulation_bridge"),
            rabbitmq=RabbitMQConfig(
                host="localhost",
                port=5672,
                virtual_host="/",
                infrastructure=RabbitMQInfrastructure(
                    exchanges=[],
                    queues=[],
                    bindings=[]
                )
            ),
            mqtt=MQTTConfig(
                host="localhost",
                port=1883,
                keepalive=60,
                input_topic="bridge/input",
                output_topic="bridge/output",
                qos=0
            ),
            rest=RESTConfig(
                host="0.0.0.0",
                port=5000,
                input_endpoint="/message",
                debug=False,
                client={
                    "host": "localhost",
                    "port": 5001,
                    "base_url": "http://localhost:5001",
                    "output_endpoint": "/result"
                }
            ),
            logging=LoggingConfig(
                level=LogLevel.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                file="logs/sim_bridge.log"
            )
        ).to_dict()

    def get_config(self) -> Dict[str, Any]:
        """
        Get the loaded configuration.

        Returns:
            Dict[str, Any]: Configuration parameters
        """
        return self.config

    def get_rabbitmq_config(self) -> Dict[str, Any]:
        """Get RabbitMQ configuration."""
        return self.config.get('rabbitmq', {})

    def get_mqtt_config(self) -> Dict[str, Any]:
        """Get MQTT configuration."""
        return self.config.get('mqtt', {})

    def get_rest_config(self) -> Dict[str, Any]:
        """Get REST configuration."""
        return self.config.get('rest', {})

    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.config.get('logging', {})
