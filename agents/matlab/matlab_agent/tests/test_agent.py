"""
Tests for the MatlabAgent class that interfaces with MATLAB simulations.
"""

import json
import pytest
from unittest import mock
from src.core.agent import MatlabAgent


@pytest.fixture
def rabbit_config():
    """Return RabbitMQ configuration for testing."""
    return {
        "host": "localhost",
        "port": 5672,
        "username": "guest",
        "password": "guest"
    }


@pytest.fixture
def config_dict(rabbit_config):
    """Return a standard configuration dictionary for testing."""
    return {
        "rabbitmq": rabbit_config
    }


@pytest.fixture
def mock_config_manager(config_dict):
    """Provide a mock instance of ConfigManager with standard configuration."""
    with mock.patch("src.core.agent.ConfigManager") as mock_cm:
        instance = mock_cm.return_value
        instance.get_config.return_value = config_dict
        yield instance


@pytest.fixture
def mock_connect():
    """Provide a mock instance of the Connect communication layer."""
    with mock.patch("src.core.agent.Connect") as mock_conn:
        instance = mock_conn.return_value
        # Ensure all expected methods are mocked
        instance.connect = mock.MagicMock()
        instance.setup = mock.MagicMock()
        instance.register_message_handler = mock.MagicMock()
        instance.start_consuming = mock.MagicMock()
        instance.close = mock.MagicMock()
        instance.send_result = mock.MagicMock(return_value=True)
        yield instance


@pytest.fixture
def mock_logger():
    """Provide a mock logger."""
    with mock.patch("src.core.agent.logger") as mock_log:
        yield mock_log


@pytest.fixture
def matlab_agent(mock_config_manager, mock_connect):
    """Create a MatlabAgent instance with mocked dependencies."""
    return MatlabAgent(agent_id="test-agent")


class TestMatlabAgentInitialization:
    """Tests for MatlabAgent initialization."""

    def test_default_initialization(
            self, matlab_agent, mock_config_manager, mock_connect):
        """Agent loads config, connects, sets up and registers handler."""
        # ConfigManager.get_config called
        mock_config_manager.get_config.assert_called_once()

        # Connect.connect and setup called
        mock_connect.connect.assert_called_once()
        mock_connect.setup.assert_called_once()

        # register_message_handler called with no args
        mock_connect.register_message_handler.assert_called_once_with()

    def test_custom_config_path_and_broker(self):
        """Initialization honors custom config_path and broker_type."""
        with mock.patch("src.core.agent.ConfigManager") as mock_cm, \
                mock.patch("src.core.agent.Connect") as mock_conn:

            # custom config_path
            mock_cm_inst = mock_cm.return_value
            mock_cm_inst.get_config.return_value = {"foo": "bar"}
            agent1 = MatlabAgent("agent1", config_path="/etc/conf.yaml")
            mock_cm.assert_called_once_with("/etc/conf.yaml")
            mock_conn.assert_called_with("agent1", {"foo": "bar"}, "rabbitmq")

            # custom broker_type
            mock_cm.reset_mock()
            mock_conn.reset_mock()
            mock_cm_inst.get_config.return_value = {"baz": 123}

            agent2 = MatlabAgent("agent2", broker_type="mqtt")
            mock_cm.assert_called_once_with(None)
            mock_conn.assert_called_with("agent2", {"baz": 123}, "mqtt")


class TestMatlabAgentOperations:
    """Tests for MatlabAgent start/stop/send_result."""

    def test_start_and_error_handling(
            self, matlab_agent, mock_connect, mock_logger):
        """start() calls start_consuming and handles different exceptions."""
        # --- Normal start ---
        matlab_agent.start()
        mock_connect.start_consuming.assert_called_once()

        # --- KeyboardInterrupt ---
        mock_connect.start_consuming.side_effect = KeyboardInterrupt
        mock_connect.start_consuming.reset_mock()
        mock_connect.close.reset_mock()
        matlab_agent.start()

        # close() deve essere chiamato in stop()
        mock_connect.close.assert_called_once()
        mock_logger.info.assert_any_call(
            "Stopping MATLAB agent due to keyboard interrupt")

        # --- Generic Exception ---
        mock_connect.start_consuming.side_effect = Exception("oops")
        mock_connect.close.reset_mock()
        mock_logger.error.reset_mock()
        mock_logger.exception.reset_mock()

        matlab_agent.start()

        # close() di nuovo chiamato
        mock_connect.close.assert_called_once()

        # Verifica che l'errore sia stato loggato con l'oggetto eccezione
        mock_logger.error.assert_any_call(
            "Unexpected error while consuming messages: %s", mock.ANY
        )
        # Verifica che sia stato loggato lo stack trace
        mock_logger.exception.assert_called_once_with("Stack trace:")

    def test_stop(self, matlab_agent, mock_connect):
        """stop() calls comm.close()."""
        matlab_agent.stop()
        mock_connect.close.assert_called_once()

    def test_send_result(self, matlab_agent, mock_connect):
        """send_result() delegates to comm.send_result."""
        data = {"value": 42}
        res = matlab_agent.send_result("dest", data)
        mock_connect.send_result.assert_called_once_with("dest", data)
        assert res is True
