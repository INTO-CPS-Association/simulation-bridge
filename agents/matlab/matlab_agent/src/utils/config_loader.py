"""
config_loader.py - Configuration loader utility

This module provides functionality to load configuration from YAML files,
with support for environment variable substitution and validation.
"""

import os
from typing import Dict, Any, Optional, Union
from pathlib import Path
from importlib import resources
import yaml
from ..utils.logger import get_logger

# Configure logger
logger = get_logger()

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / \
    "config" / "config.yaml.template"


def get_base_dir() -> Path:
    """
    Find the base directory by looking for main.py file by traversing up from the current file.

    Returns:
        Path object pointing to the base directory
    """
    current_dir: Path = Path(__file__).resolve().parent

    while current_dir.parent != current_dir:
        if (current_dir / "main.py").exists():
            return current_dir
        if (current_dir / "app.py").exists() or (current_dir / "run.py").exists():
            return current_dir
        current_dir = current_dir.parent

    cwd: Path = Path.cwd()
    if (cwd / "main.py").exists() or (cwd /
                                      "app.py").exists() or (cwd / "run.py").exists():
        return cwd

    test_dir: Path = Path(__file__).resolve().parent
    while test_dir.parent != test_dir:
        if (test_dir / "config").is_dir() and (test_dir /
                                               "config" / "config.yaml.template").exists():
            return test_dir
        test_dir = test_dir.parent

    return cwd


def load_config(
        config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
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
    if config_path is None:
        try:
            logger.debug("Loading default configuration file")
            with resources.open_text("matlab_agent.config", "config.yaml.template") as f:
                config = yaml.safe_load(f)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                "Default configuration file not found inside the package."
            ) from exc
    else:
        logger.debug("Loading configuration file from path: %s", config_path)
        config_file: Path = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_file}")
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    config = _substitute_env_vars(config)

    return config


def _substitute_env_vars(
    config: Union[Dict[str, Any], list, str]
) -> Union[Dict[str, Any], list, str]:
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
    if isinstance(config, list):
        return [_substitute_env_vars(item) for item in config]
    if isinstance(config, str) and "${" in config and "}" in config:
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


def get_config_value(config: Dict[str, Any],
                     path: str, default: Any = None) -> Any:
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
