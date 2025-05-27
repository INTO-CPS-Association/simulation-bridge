"""
Logger configuration module for the Simulation Bridge.

This module provides utilities for setting up and configuring logging functionality
with the following features:
- File logging with rotation capability
- Console logging with color-coded output
- Configurable log levels and formats

The module includes two main functions:
- setup_logger: Creates and configures a new logger instance
- get_logger: Retrieves an existing logger instance
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
import colorlog

DEFAULT_LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEFAULT_LOG_LEVEL: int = logging.INFO
MAX_LOG_SIZE: int = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT: int = 3


def setup_logger(
    name: str = 'SIMULATION-BRIDGE',
    level: int = DEFAULT_LOG_LEVEL,
    log_format: str = DEFAULT_LOG_FORMAT,
    log_file: str = 'logs/sim_bridge.log',
    enable_console: bool = True
) -> logging.Logger:
    """
    Configures a logger with handlers for file and console, with
    optional colorization for console logs.

    Args:
        name: Name of the logger
        level: Logging level
        log_format: Format of the log messages
        log_file: Path to the log file
        enable_console: Enables logging to the console with optional color

    Returns:
        Configured logger instance
    """
    logger: logging.Logger = logging.getLogger(name)
    logger.setLevel(level)

    # If the logger already has handlers, return it as is
    if logger.handlers:
        return logger

    # Ensure the log file directory exists
    log_path: Path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure file handler with rotation
    file_handler: RotatingFileHandler = RotatingFileHandler(
        filename=log_file,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter: logging.Formatter = logging.Formatter(log_format)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Configure console handler with color if enabled
    if enable_console:
        # Create a ColorFormatter for console logs
        console_handler: logging.StreamHandler = logging.StreamHandler(
            sys.stdout)
        console_handler.setLevel(level)

        # Define a colorized log format for console output
        console_format = '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        color_formatter = colorlog.ColoredFormatter(
            console_format,
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bold_red',
            }
        )

        console_handler.setFormatter(color_formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str = 'SIMULATION-BRIDGE') -> logging.Logger:
    """
    Returns an instance of the already configured logger.

    Args:
        name: Name of the logger

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
