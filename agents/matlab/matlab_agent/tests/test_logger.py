import logging
import sys
import re
from pathlib import Path
import pytest
from unittest import mock

from src.utils.logger import (
    setup_logger,
    get_logger,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_FORMAT,
    MAX_LOG_SIZE,
    BACKUP_COUNT,
)

LOG_NAME = "TEST-LOGGER"
DUMMY_LOG_FILE = "logs/test.log"


@pytest.fixture(autouse=True)
def cleanup_handlers():
    """
    Ensure logger handlers are cleaned up before and after each test
    to prevent side effects.
    """
    logger = logging.getLogger(LOG_NAME)
    original_handlers = list(logger.handlers)
    yield
    for h in list(logger.handlers):
        logger.removeHandler(h)
    for h in original_handlers:
        logger.addHandler(h)


def test_setup_logger_creates_handlers(tmp_path, monkeypatch):
    """
    Verify that setup_logger creates the correct handlers and configurations.
    """
    fake_log = tmp_path / "test.log"
    log_file_str = str(fake_log)

    mkdir_calls = []
    monkeypatch.setattr(Path, "mkdir", lambda self, **
                        kwargs: mkdir_calls.append(self))

    logger = setup_logger(
        name=LOG_NAME,
        level=logging.DEBUG,
        log_format=DEFAULT_LOG_FORMAT,
        log_file=log_file_str,
        enable_console=True,
    )

    # Verify logger name
    assert logger.name == LOG_NAME

    # Verify mkdir was called for the log directory
    assert mkdir_calls and Path(log_file_str).parent in mkdir_calls

    # Verify handler types
    types = {type(h) for h in logger.handlers}
    assert logging.handlers.RotatingFileHandler in types
    assert logging.StreamHandler in types

    # Verify RotatingFileHandler configuration
    fh = next(h for h in logger.handlers if isinstance(
        h, logging.handlers.RotatingFileHandler))
    assert fh.maxBytes == MAX_LOG_SIZE
    assert fh.backupCount == BACKUP_COUNT
    assert fh.level == logging.DEBUG

    # Verify StreamHandler configuration
    ch = next(h for h in logger.handlers if isinstance(
        h, logging.StreamHandler))
    assert ch.level == logging.DEBUG


def test_double_setup_does_not_duplicate_handlers(tmp_path):
    """
    Ensure that calling setup_logger multiple times does not duplicate handlers.
    """
    log_file_str = str(tmp_path / "test.log")
    logger1 = setup_logger(
        name=LOG_NAME, log_file=log_file_str, enable_console=False)
    count1 = len(logger1.handlers)

    logger2 = setup_logger(
        name=LOG_NAME, log_file=log_file_str, enable_console=False)
    count2 = len(logger2.handlers)

    # Verify logger instance and handler count remain consistent
    assert logger1 is logger2
    assert count1 == count2


def test_get_logger_returns_existing():
    """
    Verify that get_logger returns an existing logger instance.
    """
    logger = logging.getLogger(LOG_NAME)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)

    same = get_logger(LOG_NAME)
    # Verify logger instance and handler presence
    assert same is logger
    assert handler in same.handlers


def test_disable_console_only_file_handler(tmp_path):
    """
    Verify that setup_logger does not create a StreamHandler when enable_console=False.
    """
    log_file_str = str(tmp_path / "no_console.log")
    logger = setup_logger(
        name=LOG_NAME, log_file=log_file_str, enable_console=False)
    types = {type(h) for h in logger.handlers}
    # Verify handler types
    assert logging.StreamHandler not in types
    assert logging.handlers.RotatingFileHandler in types


def test_logger_emits_messages_with_caplog(caplog, tmp_path):
    """
    Verify that the logger emits messages and caplog captures them correctly.
    """
    log_file = tmp_path / "caplog.log"
    logger = setup_logger(
        name=LOG_NAME,
        level=logging.WARNING,
        log_format="%(levelname)s:%(message)s",  # File-specific format
        log_file=str(log_file),
        enable_console=False,
    )

    # Set caplog to capture WARNING level and above
    caplog.set_level(logging.WARNING, logger=LOG_NAME)

    # Emit an INFO message (ignored) and a WARNING message (captured)
    logger.info("ignored info")
    logger.warning("warning!")

    # Verify captured records
    assert len(caplog.records) == 1

    record = caplog.records[0]
    # Verify record level and message
    assert record.levelno == logging.WARNING
    assert record.getMessage() == "warning!"


def test_file_log_content(tmp_path):
    """
    Verify that the RotatingFileHandler writes logs to the file with correct content.
    """
    log_path = tmp_path / "file_test.log"
    logger = setup_logger(
        name=LOG_NAME,
        level=logging.ERROR,
        log_format="%(levelname)s - %(message)s",
        log_file=str(log_path),
        enable_console=False,
    )

    # Emit an error message
    logger.error("critical error")

    content = log_path.read_text()
    # Verify log file content
    assert "ERROR - critical error" in content
