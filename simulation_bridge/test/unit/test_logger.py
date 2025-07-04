"""
Unit tests for the logger module of the simulation bridge.
"""
import logging
import io
import sys
from unittest import mock

import pytest

from simulation_bridge.src.utils import logger


# pylint: disable=too-many-arguments,unused-argument,protected-access,redefined-outer-name


@pytest.fixture(autouse=True)
def clear_logger_handlers():
    """Clear handlers from the default logger before each test."""
    log = logging.getLogger('SIMULATION-BRIDGE')
    handlers = log.handlers[:]
    for h in handlers:
        log.removeHandler(h)
    yield
    # Clean up after test as well
    for h in log.handlers[:]:
        log.removeHandler(h)


@pytest.fixture
def mock_mkdir(monkeypatch):
    """Mock Path.mkdir to avoid filesystem writes."""
    m = mock.Mock()
    monkeypatch.setattr("simulation_bridge.src.utils.logger.Path.mkdir", m)
    return m


@pytest.fixture
def mock_rotating_file_handler(monkeypatch):
    """Mock RotatingFileHandler constructor."""
    m = mock.Mock()
    # Patch the RotatingFileHandler constructor inside logger module
    monkeypatch.setattr(
        "simulation_bridge.src.utils.logger.RotatingFileHandler", m)
    return m


@pytest.fixture
def mock_colorlog(monkeypatch):
    """Mock colorlog.ColoredFormatter."""
    m = mock.Mock()
    monkeypatch.setattr(
        "simulation_bridge.src.utils.logger.colorlog.ColoredFormatter", m)
    return m


@pytest.fixture
def fake_stdout(monkeypatch):
    """Replace sys.stdout with a StringIO to avoid io.UnsupportedOperation errors."""
    fake = io.StringIO()
    monkeypatch.setattr(sys, "stdout", fake)
    return fake


class TestSetupLoggerFileHandler:
    """Tests for file handler setup in setup_logger."""

    def test_rotating_file_handler_created_with_correct_args(
        self, mock_rotating_file_handler
    ):
        """Verify RotatingFileHandler is instantiated with expected parameters."""
        logger.setup_logger(log_file="logs/test.log", enable_console=False)
        mock_rotating_file_handler.assert_called_once_with(
            filename="logs/test.log",
            maxBytes=logger.MAX_LOG_SIZE,
            backupCount=logger.BACKUP_COUNT,
            encoding="utf-8",
        )


class TestSetupLoggerBehavior:
    """General behavior tests for setup_logger."""

    def test_returns_same_logger_instance_if_handlers_exist(self):
        """If logger already has handlers, setup_logger returns it without changes."""
        name = "TEST-LOGGER"
        log = logging.getLogger(name)
        handler = logging.StreamHandler()
        log.addHandler(handler)

        returned_logger = logger.setup_logger(name=name)
        assert returned_logger is log
        # Clean up added handler to maintain test isolation
        log.removeHandler(handler)

    def test_logger_level_is_set_correctly(self):
        """Logger level is set to the provided level."""
        lvl = logging.WARNING
        log = logger.setup_logger(level=lvl, enable_console=False)
        assert log.level == lvl

    def test_file_handler_level_set_to_debug(self, mock_rotating_file_handler):
        """File handler is set to DEBUG level regardless of logger level."""
        logger.setup_logger(enable_console=False)
        fh_instance = mock_rotating_file_handler.return_value
        fh_instance.setLevel.assert_called_once_with(logging.DEBUG)


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger_instance(self):
        """get_logger returns a logging.Logger instance."""
        log = logger.get_logger()
        assert isinstance(log, logging.Logger)

    def test_get_logger_returns_named_logger(self):
        """get_logger returns a logger with the correct name."""
        name = "MYLOGGER"
        log = logger.get_logger(name=name)
        assert log.name == name
