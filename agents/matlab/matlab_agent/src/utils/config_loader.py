"""Backward-compatible MATLAB config loader imports backed by base_agent."""

from base_agent.utils.config_loader import (
    default_config_path,
    get_base_dir,
    get_config_value,
    load_config,
    substitute_env_vars,
)

__all__ = [
    "default_config_path",
    "get_base_dir",
    "get_config_value",
    "load_config",
    "substitute_env_vars",
]
