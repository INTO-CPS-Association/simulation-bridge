"""Compatibility tests for MATLAB local re-export modules."""

from base_agent.comm.connect import (
    BROKER_CONNECTION_FAILED_ERROR as BASE_BROKER_CONNECTION_FAILED_ERROR,
    BROKER_NOT_INITIALIZED_ERROR as BASE_BROKER_NOT_INITIALIZED_ERROR,
    BROKER_OR_HANDLER_NOT_INITIALIZED_ERROR as BASE_BROKER_OR_HANDLER_NOT_INITIALIZED_ERROR,
    Connect as BaseConnect,
)
from base_agent.utils.config_loader import (
    default_config_path as base_default_config_path,
    get_base_dir as base_get_base_dir,
    get_config_value as base_get_config_value,
    load_config as base_load_config,
    substitute_env_vars as base_substitute_env_vars,
)
from base_agent.utils.logger import (
    BACKUP_COUNT as BASE_BACKUP_COUNT,
    DEFAULT_LOG_FORMAT as BASE_DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL as BASE_DEFAULT_LOG_LEVEL,
    MAX_LOG_SIZE as BASE_MAX_LOG_SIZE,
    get_logger as base_get_logger,
    setup_logger as base_setup_logger,
)
from matlab_agent.src.comm.connect import (
    BROKER_CONNECTION_FAILED_ERROR,
    BROKER_NOT_INITIALIZED_ERROR,
    BROKER_OR_HANDLER_NOT_INITIALIZED_ERROR,
    Connect,
)
from matlab_agent.src.utils.config_loader import (
    default_config_path,
    get_base_dir,
    get_config_value,
    load_config,
    substitute_env_vars,
)
from matlab_agent.src.utils.logger import (
    BACKUP_COUNT,
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL,
    MAX_LOG_SIZE,
    get_logger,
    setup_logger,
)


def test_connect_reexports_base_symbols() -> None:
    """MATLAB comm.connect should preserve old import paths."""

    assert Connect is BaseConnect
    assert BROKER_CONNECTION_FAILED_ERROR == BASE_BROKER_CONNECTION_FAILED_ERROR
    assert BROKER_NOT_INITIALIZED_ERROR == BASE_BROKER_NOT_INITIALIZED_ERROR
    assert BROKER_OR_HANDLER_NOT_INITIALIZED_ERROR == BASE_BROKER_OR_HANDLER_NOT_INITIALIZED_ERROR


def test_config_loader_reexports_base_symbols() -> None:
    """MATLAB utils.config_loader should preserve old import paths."""

    assert default_config_path is base_default_config_path
    assert get_base_dir is base_get_base_dir
    assert get_config_value is base_get_config_value
    assert load_config is base_load_config
    assert substitute_env_vars is base_substitute_env_vars


def test_logger_reexports_base_symbols() -> None:
    """MATLAB utils.logger should preserve old import paths."""

    assert BACKUP_COUNT == BASE_BACKUP_COUNT
    assert DEFAULT_LOG_FORMAT == BASE_DEFAULT_LOG_FORMAT
    assert DEFAULT_LOG_LEVEL == BASE_DEFAULT_LOG_LEVEL
    assert MAX_LOG_SIZE == BASE_MAX_LOG_SIZE
    assert get_logger is base_get_logger
    assert setup_logger is base_setup_logger
