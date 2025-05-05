"""
config_loader.py - Configuration loader utility

This module provides functionality to load configuration from YAML files,
with support for environment variable substitution and validation.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

def get_base_dir() -> Path:
    """
    Find the base directory by looking for main.py file by traversing up from the current file.
    
    Returns:
        Path object pointing to the base directory
    """
    # Start with the directory of the current file
    current_dir = Path(__file__).resolve().parent
    
    # Traverse up until we find main.py or reach the root
    while current_dir.parent != current_dir:  # Stop at filesystem root
        # Check if main.py exists in this directory
        if (current_dir / "main.py").exists():
            return current_dir
        
        # Also check for other common entry point files if main.py doesn't exist
        if (current_dir / "app.py").exists() or (current_dir / "run.py").exists():
            return current_dir
            
        # Move up one directory
        current_dir = current_dir.parent
    
    # If we couldn't find main.py, check the current working directory
    cwd = Path.cwd()
    if (cwd / "main.py").exists() or (cwd / "app.py").exists() or (cwd / "run.py").exists():
        return cwd
        
    # As a last resort, try to find the directory that contains the config folder
    test_dir = Path(__file__).resolve().parent
    while test_dir.parent != test_dir:  # Stop at filesystem root
        if (test_dir / "config").is_dir() and (test_dir / "config" / "config.yaml").exists():
            return test_dir
        test_dir = test_dir.parent
    
    # If all else fails, fall back to current working directory
    return cwd

# Base directory
BASE_DIR = get_base_dir()

# Default configuration file path
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "config.yaml"


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.
    
    Args:
        config_path: Path to the configuration file (optional, defaults to 'config/config.yaml')
        
    Returns:
        Dictionary containing the configuration
        
    Raises:
        FileNotFoundError: If the configuration file does not exist
        yaml.YAMLError: If the YAML file is invalid
    """
    if not config_path:
        config_path = os.environ.get("CONFIG_PATH", DEFAULT_CONFIG_PATH)
    
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Process environment variable substitutions
    config = _substitute_env_vars(config)
    
    return config

def _substitute_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively substitute environment variables in configuration values.
    Environment variables should be in the format ${ENV_VAR} or ${ENV_VAR:default_value}
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configuration with environment variables substituted
    """
    if isinstance(config, dict):
        return {k: _substitute_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_substitute_env_vars(item) for item in config]
    elif isinstance(config, str) and "${" in config and "}" in config:
        # Handle environment variable substitution
        start_idx = config.find("${")
        end_idx = config.find("}", start_idx)
        if start_idx != -1 and end_idx != -1:
            env_var = config[start_idx + 2:end_idx]
            
            # Handle default values (${ENV_VAR:default})
            if ":" in env_var:
                env_name, default = env_var.split(":", 1)
            else:
                env_name, default = env_var, ""
            
            env_value = os.environ.get(env_name, default)
            return config[:start_idx] + env_value + config[end_idx + 1:]
    
    return config

def get_config_value(config: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Get a configuration value by its dotted path.
    
    Args:
        config: Configuration dictionary
        path: Dotted path to the configuration value (e.g., 'rabbitmq.host')
        default: Default value to return if the path does not exist
        
    Returns:
        Configuration value or default
    """
    keys = path.split('.')
    value = config
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    
    return value