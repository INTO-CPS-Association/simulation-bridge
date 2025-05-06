"""
Configuration manager for the MATLAB Agent.
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from ..utils.logger import get_logger

logger = get_logger()

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
        self.config_path: Path = Path(config_path) if config_path else Path(__file__).parent.parent.parent / "config" / "config.yaml"
        self.config: Dict[str, Any] = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Returns:
            Dict[str, Any]: Configuration parameters
        """
        try:
            with open(self.config_path, 'r') as config_file:
                config: Dict[str, Any] = yaml.safe_load(config_file)
                logger.debug(f"Loaded configuration from {self.config_path}")
                return config
        except FileNotFoundError:
            logger.warning(f"Configuration file not found at {self.config_path}. Using default configuration.")
            return self.get_default_config()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file: {e}")
            logger.warning("Using default configuration instead.")
            return self.get_default_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """
        Provide default configuration if config file is not available.
        
        Returns:
            Dict[str, Any]: Default configuration parameters
        """
        default_config: Dict[str, Any] = {
            'rabbitmq': {
                'host': 'localhost',
                'port': 5672,
                'username': 'guest',
                'password': 'guest',
                'heartbeat': 600
            },
            'exchanges': {
                'input': 'ex.bridge.output',
                'output': 'ex.sim.result'
            },
            'queue': {
                'durable': True,
                'prefetch_count': 1
            }
        }
        logger.debug(f"Using default configuration")
        return default_config
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the loaded configuration.
        
        Returns:
            Dict[str, Any]: Configuration parameters
        """
        return self.config