"""Tests for shared logger utilities."""

import logging
from pathlib import Path

from base_agent.utils.logger import configure_logger


def test_configure_logger_creates_file_handler(tmp_path: Path):
    """Logger should include file handler and create log directory."""
    log_file = tmp_path / "logs" / "agent.log"
    logger_name = "BASE_LOGGER_TEST"
    logging.getLogger(logger_name).handlers.clear()

    logger = configure_logger(
        name=logger_name,
        level=logging.INFO,
        log_format="%(message)s",
        log_file=str(log_file),
        enable_console=False,
    )
    assert logger.name == logger_name
    assert log_file.parent.exists()
    assert len(logger.handlers) == 1
