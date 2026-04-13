"""MATLAB config-loader helpers built on shared base-agent utilities."""

from pathlib import Path
from typing import Any, Dict, Optional, Union

from base_agent.utils.config_loader import (
    get_base_dir as _get_base_dir,
    get_config_value as _get_config_value,
    load_config as _load_config,
    substitute_env_vars,
)

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml.template"


def load_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load MATLAB agent configuration with package template fallback."""
    return _load_config(
        package_name="matlab_agent",
        config_path=config_path,
        substitute_func=_substitute_env_vars,
    )


def _substitute_env_vars(
    config: Union[Dict[str, Any], list, str]
) -> Union[Dict[str, Any], list, str]:
    """Backwards-compatible alias for internal test patching."""
    return substitute_env_vars(config)


def get_base_dir() -> Path:
    """Backwards-compatible wrapper for shared base-dir discovery."""
    return _get_base_dir()


def get_config_value(
    config: Dict[str, Any],
    path: str,
    default: Any = None,
) -> Any:
    """Backwards-compatible wrapper for shared dotted-path value lookup."""
    return _get_config_value(config, path, default)
