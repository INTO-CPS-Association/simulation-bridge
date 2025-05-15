import logging
from unittest.mock import MagicMock, patch
import pytest
from click.testing import CliRunner

from src.main import main, run_single_agent


class TestMainFunction:
    """Test suite for the main function and related functionalities."""

    @pytest.fixture
    def default_config(self):
        """Default configuration for tests."""
        return {
            'logging': {'level': 'INFO', 'file': 'app.log'},
            'agent': {'agent_id': 'default_agent'}
        }

    @pytest.fixture
    def custom_config(self):
        """Custom configuration for tests."""
        return {
            'logging': {'level': 'DEBUG', 'file': 'debug.log'},
            'agent': {'agent_id': 'custom_agent'}
        }

    @pytest.fixture
    def invalid_log_config(self):
        """Configuration with an invalid log level."""
        return {
            'logging': {'level': 'INVALID', 'file': 'app.log'},
            'agent': {'agent_id': 'agent_x'}
        }

    @pytest.fixture
    def missing_agent_config(self):
        """Configuration with a missing agent_id."""
        return {
            'logging': {'level': 'INFO', 'file': 'app.log'},
            'agent': {}  # Missing agent_id
        }

    @pytest.fixture
    def mock_agent(self):
        """Mock for the agent object."""
        agent = MagicMock()
        agent.start = MagicMock()
        agent.stop = MagicMock()
        return agent

    @pytest.fixture
    def cli_runner(self):
        """Runner for testing CLI commands."""
        return CliRunner()

    @pytest.fixture
    def mock_dependencies(self, mock_agent):
        """Mock for all main dependencies."""
        with patch('src.main.MatlabAgent') as MockAgent, \
                patch('src.main.setup_logger') as mock_setup_logger, \
                patch('src.main.load_config') as mock_load_config:

            MockAgent.return_value = mock_agent
            yield MockAgent, mock_setup_logger, mock_load_config

    def test_main_with_config_file(
            self,
            cli_runner,
            mock_dependencies,
            custom_config):
        """Test main with a specified configuration file."""
        MockAgent, mock_setup_logger, mock_load_config = mock_dependencies
        mock_load_config.return_value = custom_config

        config_path = 'matlab_agent/config/config.yaml'
        result = cli_runner.invoke(main, ['-c', config_path])

        mock_load_config.assert_called_once_with(config_path)
        MockAgent.assert_called_once_with('custom_agent')
        mock_agent = MockAgent.return_value
        mock_agent.start.assert_called_once()
        assert result.exit_code == 0

    def test_main_without_config_file(
            self,
            cli_runner,
            mock_dependencies,
            default_config):
        """Test main without specifying a configuration file."""
        MockAgent, mock_setup_logger, mock_load_config = mock_dependencies
        mock_load_config.return_value = default_config

        result = cli_runner.invoke(main, [])

        mock_load_config.assert_called_once_with(None)
        MockAgent.assert_called_once_with('default_agent')
        mock_agent = MockAgent.return_value
        mock_agent.start.assert_called_once()
        assert result.exit_code == 0

    def test_main_keyboard_interrupt(
            self,
            cli_runner,
            mock_dependencies,
            default_config):
        """Test keyboard interruption during main execution."""
        MockAgent, mock_setup_logger, mock_load_config = mock_dependencies
        mock_load_config.return_value = default_config

        # Simulate KeyboardInterrupt in start()
        mock_agent = MockAgent.return_value
        mock_agent.start.side_effect = KeyboardInterrupt()

        result = cli_runner.invoke(main, [])

        mock_agent.stop.assert_called_once()
        assert result.exit_code == 0

    def test_main_general_error(
            self,
            cli_runner,
            mock_dependencies,
            default_config):
        """Test a general error during main execution."""
        MockAgent, mock_setup_logger, mock_load_config = mock_dependencies
        mock_load_config.return_value = default_config

        # Simulate a general error in start()
        mock_agent = MockAgent.return_value
        mock_agent.start.side_effect = Exception("Simulated failure")

        result = cli_runner.invoke(main, [])

        mock_agent.stop.assert_called_once()
        assert result.exit_code == 0

    def test_invalid_log_level(
            self,
            cli_runner,
            mock_dependencies,
            invalid_log_config):
        """Test behavior with an invalid log level (fallback to INFO)."""
        MockAgent, mock_setup_logger, mock_load_config = mock_dependencies
        mock_load_config.return_value = invalid_log_config

        result = cli_runner.invoke(main, [])

        mock_setup_logger.assert_called_once_with(
            level=logging.INFO,
            log_file='app.log'
        )
        assert result.exit_code == 0

    def test_missing_agent_id(
            self,
            cli_runner,
            mock_dependencies,
            missing_agent_config):
        """Test behavior with a missing agent_id in the configuration."""
        MockAgent, mock_setup_logger, mock_load_config = mock_dependencies
        mock_load_config.return_value = missing_agent_config

        result = cli_runner.invoke(main, [])

        # Should fail if agent_id is missing
        assert result.exit_code != 0

    def test_run_single_agent_direct(self, mock_dependencies, custom_config):
        """Directly test the run_single_agent function."""
        MockAgent, mock_setup_logger, mock_load_config = mock_dependencies
        mock_load_config.return_value = custom_config

        run_single_agent('test_config.yml')

        mock_load_config.assert_called_once_with('test_config.yml')
        MockAgent.assert_called_once_with('custom_agent')
        mock_agent = MockAgent.return_value
        mock_agent.start.assert_called_once()
