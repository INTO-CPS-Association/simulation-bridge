"""
config_manager.py - Configuration manager utility

This module provides functionality to load and manage application configuration
using Pydantic models for validation and nested structure.
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from pathlib import Path
from pydantic import BaseModel, ValidationError, ConfigDict

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
    endpoint: str
    certfile: str
    keyfile: str
    debug: bool


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
        """Create a Config instance from a nested dictionary.

        This method correctly handles nested models by constructing each
        sub-model separately before assembling the final Config object.
        """
        # Process nested dictionaries into their respective model types
        sim_bridge_config = SimulationBridgeConfig(
            **config_dict.get('simulation_bridge', {}))

        # Process RabbitMQ configuration with its nested infrastructure
        rabbitmq_dict = config_dict.get('rabbitmq', {})
        infra_dict = rabbitmq_dict.get('infrastructure', {})

        # Create infrastructure objects
        infrastructure = RabbitMQInfrastructure(
            exchanges=[ExchangeConfig(**exc)
                       for exc in infra_dict.get('exchanges', [])],
            queues=[QueueConfig(**queue)
                    for queue in infra_dict.get('queues', [])],
            bindings=[BindingConfig(**binding)
                      for binding in infra_dict.get('bindings', [])]
        )

        # Create RabbitMQ config with the infrastructure
        rabbit_config = RabbitMQConfig(
            host=rabbitmq_dict.get('host', 'localhost'),
            port=rabbitmq_dict.get('port', 5672),
            virtual_host=rabbitmq_dict.get('virtual_host', '/'),
            infrastructure=infrastructure
        )

        # Create remaining configs
        mqtt_config = MQTTConfig(**config_dict.get('mqtt', {}))
        rest_config = RESTConfig(**config_dict.get('rest', {}))
        logging_config = LoggingConfig(**config_dict.get('logging', {}))

        # Assemble and return the complete Config object
        return cls(
            simulation_bridge=sim_bridge_config,
            rabbitmq=rabbit_config,
            mqtt=mqtt_config,
            rest=rest_config,
            logging=logging_config
        )


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
            logger.warning("Using defaults value: %s", str(e))
            self.config = self.get_default_config()
        except (IOError, PermissionError) as e:
            logger.error("File access error: %s, using defaults.", str(e))
            self.config = self.get_default_config()
        except Exception as e: # pylint: disable=broad-exception-caught
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
            simulation_bridge=SimulationBridgeConfig(
                bridge_id="simulation_bridge"),
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
                endpoint="/message",
                certfile="./certs/cert.pem",
                keyfile="./certs/key.pem",
                debug=False
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
