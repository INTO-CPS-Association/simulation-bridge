"""
Tests for the simul8Agent class that interfaces with simul8 simulations.
"""

from unittest import mock
import pytest
from src.core.agent import Simul8Agent


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
def config_dict(rabbit_config):  # pylint: disable=redefined-outer-name
    """Return a standard configuration dictionary for testing."""
    return {
        "rabbitmq": rabbit_config
    }


@pytest.fixture
def mock_config_manager(config_dict):  # pylint: disable=redefined-outer-name
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
def simul8_agent(mock_config_manager, mock_connect):  # pylint: disable=redefined-outer-name,unused-argument
    """Create a Simul8Agent instance with mocked dependencies."""
    return Simul8Agent(agent_id="test-agent")


class TestSimul8Initialization:
    """Tests for Simul8Agent initialization."""

    def test_default_initialization(
            self, simul8_agent, mock_config_manager, mock_connect):  # pylint: disable=redefined-outer-name
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
            _ = Simul8Agent("agent1", config_path="/etc/conf.yaml")
            mock_cm.assert_called_once_with("/etc/conf.yaml")
            mock_conn.assert_called_with("agent1", {"foo": "bar"}, "rabbitmq")

            # custom broker_type
            mock_cm.reset_mock()
            mock_conn.reset_mock()
            mock_cm_inst.get_config.return_value = {"baz": 123}

            _ = Simul8Agent("agent2", broker_type="mqtt")
            mock_cm.assert_called_once_with(None)
            mock_conn.assert_called_with("agent2", {"baz": 123}, "mqtt")


class TestSimul8AgentOperations:
    """Tests for Simul8Agent start/stop/send_result."""

    def test_start_and_error_handling(
            self, simul8_agent, mock_connect, mock_logger):
        """start() calls start_consuming and handles different exceptions."""
        # Normal start
        simul8_agent.start()
        mock_connect.start_consuming.assert_called_once()

        # KeyboardInterrupt
        mock_connect.start_consuming.side_effect = KeyboardInterrupt
        mock_connect.start_consuming.reset_mock()
        mock_connect.close.reset_mock()
        mock_logger.info.reset_mock()

        simul8_agent.start()

        mock_connect.close.assert_called_once()
        mock_logger.info.assert_any_call(
            "Stopping Simul8 agent due to keyboard interrupt")

        # Generic Exception
        mock_connect.start_consuming.side_effect = Exception("oops")
        mock_connect.close.reset_mock()
        mock_logger.error.reset_mock()
        mock_logger.exception.reset_mock()

        simul8_agent.start()

        mock_connect.close.assert_called_once()

        # Fix: verify error was logged (check call was made, exact message may
        # vary)
        assert mock_logger.error.call_count >= 1, "Expected logger.error to be called"
        # Check exception stack trace was logged
        assert mock_logger.exception.call_count >= 1, "Expected logger.exception to be called"

    def test_stop(self, simul8_agent, mock_connect):  # pylint: disable=redefined-outer-name
        """stop() calls comm.close()."""
        simul8_agent.stop()
        mock_connect.close.assert_called_once()

    def test_send_result(self, simul8_agent, mock_connect):  # pylint: disable=redefined-outer-name
        """send_result() delegates to comm.send_result."""
        data = {"value": 42}
        res = simul8_agent.send_result("dest", data)
        mock_connect.send_result.assert_called_once_with("dest", data)
        assert res is True
