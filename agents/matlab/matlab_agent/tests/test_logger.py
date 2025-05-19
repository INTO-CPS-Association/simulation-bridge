import logging
import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from src.utils.logger import (
    BACKUP_COUNT, DEFAULT_LOG_FORMAT, MAX_LOG_SIZE,
    get_logger, setup_logger
)

LOG_NAME = "TEST-LOGGER"


@pytest.fixture
def temp_log_file(tmp_path):
    """Create a temporary log file path."""
    log_path = tmp_path / "test.log"
    return str(log_path)


@pytest.fixture
def logger_cleanup():
    """
    Ensure that logger handlers are cleaned up before and after each test
    to prevent side effects.
    """
    logger = logging.getLogger(LOG_NAME)
    original_handlers = list(logger.handlers)
    yield
    # Cleanup: remove all handlers added during the test
    for h in list(logger.handlers):
        if h not in original_handlers:
            logger.removeHandler(h)


@pytest.fixture
def mock_log_path(monkeypatch):
    """Mock for Path.mkdir calls."""
    mkdir_calls = []
    monkeypatch.setattr(Path, "mkdir", lambda self, **
                        kwargs: mkdir_calls.append(self))
    return mkdir_calls


class TestLogger:
    """Test suite for logging functionality."""

    def test_setup_logger_creates_handlers(
            self, temp_log_file, mock_log_path, logger_cleanup):
        """Verify that setup_logger creates the correct handlers with the right configurations."""
        logger = setup_logger(
            name=LOG_NAME,
            level=logging.DEBUG,
            log_format=DEFAULT_LOG_FORMAT,
            log_file=temp_log_file,
            enable_console=True,
        )

        # Verify logger name
        assert logger.name == LOG_NAME

        # Verify that mkdir was called for the log directory
        assert mock_log_path and Path(temp_log_file).parent in mock_log_path

        # Verify handler types
        handler_types = {type(h) for h in logger.handlers}
        assert logging.handlers.RotatingFileHandler in handler_types
        assert logging.StreamHandler in handler_types

        # Verify RotatingFileHandler configuration
        file_handler = next(
            h for h in logger.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        )
        assert file_handler.maxBytes == MAX_LOG_SIZE
        assert file_handler.backupCount == BACKUP_COUNT
        assert file_handler.level == logging.DEBUG

        # Verify StreamHandler configuration
        console_handler = next(
            h for h in logger.handlers if isinstance(h, logging.StreamHandler)
        )
        assert console_handler.level == logging.DEBUG

    def test_double_setup_does_not_duplicate_handlers(
            self, temp_log_file, logger_cleanup):
        """Ensure that calling setup_logger multiple times does not duplicate handlers."""
        logger1 = setup_logger(
            name=LOG_NAME, log_file=temp_log_file, enable_console=False
        )
        count1 = len(logger1.handlers)

        logger2 = setup_logger(
            name=LOG_NAME, log_file=temp_log_file, enable_console=False
        )
        count2 = len(logger2.handlers)

        # Verify that the logger instance and handler count remain consistent
        assert logger1 is logger2
        assert count1 == count2

    def test_get_logger_returns_existing(self, logger_cleanup):
        """Verify that get_logger returns an existing logger instance."""
        logger = logging.getLogger(LOG_NAME)
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)

        same_logger = get_logger(LOG_NAME)
        # Verify logger instance and presence of the handler
        assert same_logger is logger
        assert handler in same_logger.handlers

    def test_disable_console_only_file_handler(
            self, temp_log_file, logger_cleanup):
        """Verify that setup_logger does not create a StreamHandler when enable_console=False."""
        logger = setup_logger(
            name=LOG_NAME, log_file=temp_log_file, enable_console=False
        )
        handler_types = {type(h) for h in logger.handlers}
        # Verify handler types
        assert logging.StreamHandler not in handler_types
        assert logging.handlers.RotatingFileHandler in handler_types

    def test_logger_emits_messages_with_caplog(
            self, caplog, temp_log_file, logger_cleanup):
        """Verify that the logger emits messages and caplog captures them correctly."""
        logger = setup_logger(
            name=LOG_NAME,
            level=logging.WARNING,
            # Specific format for the file
            log_format="%(levelname)s:%(message)s",
            log_file=temp_log_file,
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

    def test_file_log_content(self, temp_log_file, logger_cleanup):
        """Verify that RotatingFileHandler writes logs with the correct content."""
        logger = setup_logger(
            name=LOG_NAME,
            level=logging.ERROR,
            log_format="%(levelname)s - %(message)s",
            log_file=temp_log_file,
            enable_console=False,
        )

        # Emit an error message
        logger.error("critical error")

        # Read the content of the log file
        with open(temp_log_file, 'r') as log_file:
            content = log_file.read()

        # Verify the content of the log file
        assert "ERROR - critical error" in content
