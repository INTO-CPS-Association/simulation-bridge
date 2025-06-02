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
            with resources.open_text("simulation_bridge.config", "config.yaml") as f:
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
