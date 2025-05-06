"""
Configuration manager for the MATLAB Agent.
"""

import yaml
from pathlib import Path
from ..utils.logger import get_logger

logger = get_logger()

class ConfigManager:
    """
    Manager for loading and providing access to application configuration.
    """
    def __init__(self, config_path=None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path (str, optional): Path to the configuration file.
                                         If None, uses the default location.
        """
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "config.yaml"
        self.config = self.load_config()
    
    def load_config(self):
        """
        Load configuration from YAML file.
        
        Returns:
            dict: Configuration parameters
        """
        try:
            with open(self.config_path, 'r') as config_file:
                config = yaml.safe_load(config_file)
                logger.debug(f"Loaded configuration from {self.config_path}")
                return config
        except FileNotFoundError:
            logger.warning(f"Configuration file not found at {self.config_path}. Using default configuration.")
            return self.get_default_config()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file: {e}")
            logger.warning("Using default configuration instead.")
            return self.get_default_config()
    
    def get_default_config(self):
        """
        Provide default configuration if config file is not available.
        
        Returns:
            dict: Default configuration parameters
        """
        default_config = {
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
    
    def get_config(self):
        """
        Get the loaded configuration.
        
        Returns:
            dict: Configuration parameters
        """
        return self.config