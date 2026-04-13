"""Shared configuration loader utilities for simulation agents."""

import os
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

import yaml


def default_config_path() -> Path:
    """Return the default config template path relative to an agent package layout."""
    return Path(__file__).parent.parent / "config" / "config.yaml.template"


def get_base_dir() -> Path:
    """Find an executable project base directory by walking parents and cwd."""
    current_dir = Path(__file__).resolve().parent
    while current_dir.parent != current_dir:
        if (current_dir / "main.py").exists():
            return current_dir
        if (current_dir / "app.py").exists() or (current_dir / "run.py").exists():
            return current_dir
        current_dir = current_dir.parent

    cwd = Path.cwd()
    if (cwd / "main.py").exists() or (cwd / "app.py").exists() or (cwd / "run.py").exists():
        return cwd

    test_dir = Path(__file__).resolve().parent
    while test_dir.parent != test_dir:
        template_path = test_dir / "config" / "config.yaml.template"
        if (test_dir / "config").is_dir() and template_path.exists():
            return test_dir
        test_dir = test_dir.parent

    return cwd


def load_config(
    package_name: str,
    config_path: Optional[Union[str, Path]] = None,
    substitute_func: Optional[
        Callable[[Union[Dict[str, Any], list, str]], Union[Dict[str, Any], list, str]]
    ] = None,
) -> Dict[str, Any]:
    """Load config from an explicit path or package template, then substitute env vars."""
    if config_path is None:
        try:
            with resources.open_text(
                f"{package_name}.config",
                "config.yaml.template",
            ) as config_file:
                config = yaml.safe_load(config_file)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                "Default configuration file not found inside the package."
            ) from exc
    else:
        config_file_path = Path(config_path)
        if not config_file_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_file_path}"
            )
        with open(config_file_path, "r", encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file)

    substitution_fn = substitute_func or substitute_env_vars
    return substitution_fn(config)


def substitute_env_vars(
    config: Union[Dict[str, Any], list, str]
) -> Union[Dict[str, Any], list, str]:
    """Recursively substitute ${ENV} and ${ENV:default} placeholders."""
    if isinstance(config, dict):
        return {key: substitute_env_vars(value) for key, value in config.items()}
    if isinstance(config, list):
        return [substitute_env_vars(item) for item in config]
    if isinstance(config, str) and "${" in config and "}" in config:
        start_idx = config.find("${")
        end_idx = config.find("}", start_idx)
        if start_idx != -1 and end_idx != -1:
            env_var = config[start_idx + 2:end_idx]
            if ":" in env_var:
                env_name, default = env_var.split(":", 1)
            else:
                env_name, default = env_var, ""
            env_value = os.environ.get(env_name, default)
            return config[:start_idx] + env_value + config[end_idx + 1:]
    return config


def get_config_value(config: Dict[str, Any], path: str, default: Any = None) -> Any:
    """Get a nested configuration value via dotted path, or default when missing."""
    value: Any = config
    for key in path.split("."):
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value
