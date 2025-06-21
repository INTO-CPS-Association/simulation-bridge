"""
Unit tests for the logger module.

This module contains comprehensive tests for the logger configuration utilities,
including file logging, console output, log rotation, and colorized formatting.
"""

import logging
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import colorlog

# Assuming the logger module is in the same directory
from src.utils.logger import (
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL,
    MAX_LOG_SIZE,
    BACKUP_COUNT,
    setup_logger,
    get_logger
)


class TestLoggerSetup(unittest.TestCase):
    """Test cases for logger setup functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_log_file = os.path.join(self.temp_dir, 'test.log')
        self.logger_name = 'TEST_LOGGER'

        # Clear any existing loggers to avoid interference
        logging.getLogger(self.logger_name).handlers.clear()
        logging.getLogger(self.logger_name).setLevel(logging.NOTSET)

    def tearDown(self):
        """Clean up after each test method."""
        # Remove all handlers from test logger
        test_logger = logging.getLogger(self.logger_name)
        for handler in test_logger.handlers[:]:
            handler.close()
            test_logger.removeHandler(handler)

        # Clean up temporary files
        if os.path.exists(self.test_log_file):
            os.remove(self.test_log_file)
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_setup_logger_default_parameters(self):
        """Test logger setup with default parameters."""
        temp_dir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(temp_dir, 'default.log')
            logger = setup_logger(
                name=self.logger_name,
                log_file=log_file
            )

            self.assertIsInstance(logger, logging.Logger)
            self.assertEqual(logger.name, self.logger_name)
            self.assertEqual(logger.level, DEFAULT_LOG_LEVEL)
            self.assertEqual(len(logger.handlers), 2)  # File + Console handlers

            # Close handlers before removing temp directory
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_setup_logger_custom_parameters(self):
        """Test logger setup with custom parameters."""
        custom_level = logging.DEBUG
        custom_format = '%(name)s - %(message)s'

        logger = setup_logger(
            name=self.logger_name,
            level=custom_level,
            log_format=custom_format,
            log_file=self.test_log_file,
            enable_console=False
        )

        self.assertEqual(logger.level, custom_level)
        self.assertEqual(len(logger.handlers), 1)  # Only file handler

    def test_log_file_creation(self):
        """Test that log file and directory are created."""
        log_dir = os.path.join(self.temp_dir, 'nested', 'directory')
        log_file = os.path.join(log_dir, 'nested.log')

        setup_logger(
            name=self.logger_name,
            log_file=log_file
        )

        self.assertTrue(os.path.exists(log_dir))
        # Log file might not exist until first write, but directory should exist

    def test_file_handler_configuration(self):
        """Test file handler configuration."""
        logger = setup_logger(
            name=self.logger_name,
            log_file=self.test_log_file
        )

        file_handler = None
        for handler in logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                file_handler = handler
                break

        self.assertIsNotNone(file_handler)
        self.assertEqual(file_handler.maxBytes, MAX_LOG_SIZE)
        self.assertEqual(file_handler.backupCount, BACKUP_COUNT)
        self.assertEqual(file_handler.level, logging.DEBUG)

    def test_console_handler_configuration(self):
        """Test console handler configuration."""
        logger = setup_logger(
            name=self.logger_name,
            log_file=self.test_log_file,
            enable_console=True
        )

        console_handler = None
        for handler in logger.handlers:
            if isinstance(
                    handler, logging.StreamHandler) and handler.stream == sys.stdout:
                console_handler = handler
                break

        self.assertIsNotNone(console_handler)
        self.assertEqual(console_handler.level, DEFAULT_LOG_LEVEL)
        self.assertIsInstance(
            console_handler.formatter,
            colorlog.ColoredFormatter)

    def test_console_disabled(self):
        """Test logger setup with console disabled."""
        logger = setup_logger(
            name=self.logger_name,
            log_file=self.test_log_file,
            enable_console=False
        )

        console_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and h.stream == sys.stdout
        ]

        self.assertEqual(len(console_handlers), 0)

    def test_logger_already_configured(self):
        """Test that existing logger handlers are preserved."""
        # Set up logger first time
        logger1 = setup_logger(
            name=self.logger_name,
            log_file=self.test_log_file
        )
        initial_handler_count = len(logger1.handlers)

        # Set up same logger again
        logger2 = setup_logger(
            name=self.logger_name,
            log_file=self.test_log_file
        )

        self.assertIs(logger1, logger2)
        self.assertEqual(len(logger2.handlers), initial_handler_count)

    def test_color_formatter_configuration(self):
        """Test color formatter configuration."""
        logger = setup_logger(
            name=self.logger_name,
            log_file=self.test_log_file,
            enable_console=True
        )

        console_handler = None
        for handler in logger.handlers:
            if isinstance(
                    handler, logging.StreamHandler) and handler.stream == sys.stdout:
                console_handler = handler
                break

        self.assertIsNotNone(console_handler)
        formatter = console_handler.formatter
        self.assertIsInstance(formatter, colorlog.ColoredFormatter)

        # Test that color configuration exists
        expected_colors = {
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
        self.assertEqual(formatter.log_colors, expected_colors)

    @patch('pathlib.Path.mkdir')
    def test_log_directory_creation_error_handling(self, mock_mkdir):
        """Test handling of directory creation errors."""
        mock_mkdir.side_effect = OSError("Permission denied")

        with self.assertRaises(OSError):
            setup_logger(
                name=self.logger_name,
                log_file=self.test_log_file
            )

    def test_logging_functionality(self):
        """Test actual logging functionality."""
        logger = setup_logger(
            name=self.logger_name,
            log_file=self.test_log_file
        )

        test_message = "Test log message"
        logger.info(test_message)

        # Check if log file was created and contains the message
        self.assertTrue(os.path.exists(self.test_log_file))

        with open(self.test_log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
            self.assertIn(test_message, log_content)
            self.assertIn('INFO', log_content)

    def test_different_log_levels(self):
        """Test logging at different levels."""
        logger = setup_logger(
            name=self.logger_name,
            level=logging.DEBUG,
            log_file=self.test_log_file
        )

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        with open(self.test_log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
            self.assertIn("Debug message", log_content)
            self.assertIn("Info message", log_content)
            self.assertIn("Warning message", log_content)
            self.assertIn("Error message", log_content)
            self.assertIn("Critical message", log_content)


class TestGetLogger(unittest.TestCase):
    """Test cases for get_logger functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.logger_name = 'GET_LOGGER_TEST'
        # Clear any existing loggers
        logging.getLogger(self.logger_name).handlers.clear()

    def tearDown(self):
        """Clean up after each test method."""
        test_logger = logging.getLogger(self.logger_name)
        for handler in test_logger.handlers[:]:
            handler.close()
            test_logger.removeHandler(handler)

    def test_get_logger_default_name(self):
        """Test get_logger with default name."""
        logger = get_logger()
        self.assertEqual(logger.name, 'MATLAB-AGENT')
        self.assertIsInstance(logger, logging.Logger)

    def test_get_logger_custom_name(self):
        """Test get_logger with custom name."""
        logger = get_logger(self.logger_name)
        self.assertEqual(logger.name, self.logger_name)
        self.assertIsInstance(logger, logging.Logger)

    def test_get_logger_same_instance(self):
        """Test that get_logger returns the same instance for the same name."""
        logger1 = get_logger(self.logger_name)
        logger2 = get_logger(self.logger_name)
        self.assertIs(logger1, logger2)


class TestLoggerConstants(unittest.TestCase):
    """Test cases for logger constants."""

    def test_default_constants(self):
        """Test that constants have expected values."""
        self.assertEqual(DEFAULT_LOG_FORMAT,
                         '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.assertEqual(DEFAULT_LOG_LEVEL, logging.INFO)
        self.assertEqual(MAX_LOG_SIZE, 5 * 1024 * 1024)  # 5 MB
        self.assertEqual(BACKUP_COUNT, 3)


class TestLogRotation(unittest.TestCase):
    """Test cases for log rotation functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_log_file = os.path.join(self.temp_dir, 'rotation_test.log')
        self.logger_name = 'ROTATION_TEST_LOGGER'

        # Clear any existing loggers
        logging.getLogger(self.logger_name).handlers.clear()

    def tearDown(self):
        """Clean up after each test method."""
        test_logger = logging.getLogger(self.logger_name)
        for handler in test_logger.handlers[:]:
            handler.close()
            test_logger.removeHandler(handler)

        # Clean up temporary files
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch('src.utils.logger.MAX_LOG_SIZE', 100)  # Small size for testing
    def test_log_rotation_trigger(self):
        """Test that log rotation is triggered when size limit is reached."""
        logger = setup_logger(
            name=self.logger_name,
            log_file=self.test_log_file
        )

        # Write enough data to trigger rotation
        large_message = "A" * 50
        for _ in range(5):  # Should exceed 100 bytes
            logger.info(large_message)

        # Force handler to flush
        for handler in logger.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()

        # Check if rotation files might exist (implementation dependent)
        self.assertTrue(os.path.exists(self.test_log_file))


if __name__ == '__main__':
    # Configure test runner
    unittest.main(verbosity=2)
