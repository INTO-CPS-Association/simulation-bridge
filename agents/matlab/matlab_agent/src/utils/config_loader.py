"""
config_loader.py - Configuration loader utility

This module provides functionality to load configuration from YAML files,
with support for environment variable substitution and validation.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from yaml import SafeLoader  # Requires types-PyYAML for type hints

def get_base_dir() -> Path:
    """
    Find the base directory by looking for main.py file by traversing up from the current file.
    
    Returns:
        Path object pointing to the base directory
    """
    current_dir: Path = Path(__file__).resolve().parent
    
    while current_dir.parent != current_dir:  # Stop at filesystem root
        if (current_dir / "main.py").exists():
            return current_dir
        if (current_dir / "app.py").exists() or (current_dir / "run.py").exists():
            return current_dir
        current_dir = current_dir.parent
    
    cwd: Path = Path.cwd()
    if (cwd / "main.py").exists() or (cwd / "app.py").exists() or (cwd / "run.py").exists():
        return cwd
    
    test_dir: Path = Path(__file__).resolve().parent
    while test_dir.parent != test_dir:  # Stop at filesystem root
        if (test_dir / "config").is_dir() and (test_dir / "config" / "config.yaml").exists():
            return test_dir
        test_dir = test_dir.parent
    
    return cwd

# Base directory
BASE_DIR: Path = get_base_dir()

# Default configuration file path
DEFAULT_CONFIG_PATH: Path = BASE_DIR.parent / "config" / "config.yaml"


def load_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
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
    
    config_file: Path = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    with open(config_file, 'r') as f:
        config: Dict[str, Any] = yaml.load(f, Loader=SafeLoader)
    
    config = _substitute_env_vars(config)
    
    return config

def _substitute_env_vars(config: Union[Dict[str, Any], list, str]) -> Union[Dict[str, Any], list, str]:
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
        start_idx: int = config.find("${")
        end_idx: int = config.find("}", start_idx)
        if start_idx != -1 and end_idx != -1:
            env_var: str = config[start_idx + 2:end_idx]
            
            if ":" in env_var:
                env_name, default = env_var.split(":", 1)
            else:
                env_name, default = env_var, ""
            
            env_value: str = os.environ.get(env_name, default)
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
    keys: list[str] = path.split('.')
    value: Any = config
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    
    return value
