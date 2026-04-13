"""MATLAB logger helpers built on shared base-agent utilities."""

import logging

from base_agent.utils.logger import (
    DEFAULT_BACKUP_COUNT as _DEFAULT_BACKUP_COUNT,
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_LOG_SIZE as _DEFAULT_MAX_LOG_SIZE,
    configure_logger,
)

MAX_LOG_SIZE: int = _DEFAULT_MAX_LOG_SIZE
BACKUP_COUNT: int = _DEFAULT_BACKUP_COUNT


def setup_logger(
    name: str = "MATLAB-AGENT",
    level: int = DEFAULT_LOG_LEVEL,
    log_format: str = DEFAULT_LOG_FORMAT,
    log_file: str = "logs/matlab-agent.log",
    enable_console: bool = True,
) -> logging.Logger:
    """Configure MATLAB logger with agent defaults."""
    return configure_logger(
        name=name,
        level=level,
        log_format=log_format,
        log_file=log_file,
        enable_console=enable_console,
        max_log_size=MAX_LOG_SIZE,
        backup_count=BACKUP_COUNT,
    )


def get_logger(name: str = "MATLAB-AGENT") -> logging.Logger:
    """Return logger instance by name."""
    return logging.getLogger(name)
