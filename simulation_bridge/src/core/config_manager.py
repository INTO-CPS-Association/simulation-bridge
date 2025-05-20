# config_manager.py - Gestione configurazione YAML
import yaml
from typing import Optional, Dict, Any, Literal
from pathlib import Path
from enum import Enum
from pydantic import BaseModel, Field, ValidationError, ConfigDict

from ..utils.logger import get_logger
from ..utils.config_loader import load_config

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
    simulation_bridge_id: str = Field(default="simulation_bridge")

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary with nested structure."""
        return {
            ## Add fields here
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'Config':
        """Create a Config instance from a nested dictionary."""
        # Extract values from nested structure
        flat_config = {
            ## Add fields here
        }

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
            __file__).parent.parent.parent / "config" / "config.yaml.template"
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

    def get_rabbitmq_config(self):
        return self.config.get('rabbitmq', {})

    def get_infrastructure_config(self):
        return self.config.get('infrastructure', {})
