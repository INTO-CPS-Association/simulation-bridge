"""Shared logger configuration utilities for simulation agents."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import colorlog

DEFAULT_LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LOG_LEVEL: int = logging.INFO
DEFAULT_MAX_LOG_SIZE: int = 5 * 1024 * 1024  # 5 MB
DEFAULT_BACKUP_COUNT: int = 3


def configure_logger(
    name: str,
    level: int,
    log_format: str,
    log_file: str,
    enable_console: bool,
    max_log_size: int = DEFAULT_MAX_LOG_SIZE,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> logging.Logger:
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    """Create (or return) a configured logger with rotating file and console handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=max_log_size,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(file_handler)

    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(
            colorlog.ColoredFormatter(
                "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                },
            )
        )
        logger.addHandler(console_handler)

    return logger
