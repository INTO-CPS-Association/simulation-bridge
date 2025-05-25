import os
import logging
from unittest.mock import MagicMock, patch
import pytest
from click.testing import CliRunner

from src.main import main, run_agent


class TestMainFunction:
    """Test suite for the main function and related functionalities."""

    @pytest.fixture
    def default_config(self):
        return {
            'logging': {'level': 'INFO', 'file': 'app.log'},
            'agent': {'agent_id': 'default_agent'}
        }

    @pytest.fixture
    def custom_config(self):
        return {
            'logging': {'level': 'DEBUG', 'file': 'debug.log'},
            'agent': {'agent_id': 'custom_agent'}
        }

    @pytest.fixture
    def invalid_log_config(self):
        return {
            'logging': {'level': 'INVALID', 'file': 'app.log'},
            'agent': {'agent_id': 'agent_x'}
        }

    @pytest.fixture
    def missing_agent_config(self):
        return {
            'logging': {'level': 'INFO', 'file': 'app.log'},
            'agent': {}
        }

    @pytest.fixture
    def mock_agent(self):
        agent = MagicMock()
        agent.start = MagicMock()
        agent.stop = MagicMock()
        return agent

    @pytest.fixture
    def cli_runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_dependencies(self, mock_agent):
        with patch('src.main.MatlabAgent') as MockAgent, \
                patch('src.main.setup_logger') as mock_setup_logger, \
                patch('src.main.load_config') as mock_load_config:

            # Setup mock logger with debug/info/error methods
            mock_logger = MagicMock()
            mock_logger.debug = MagicMock()
            mock_logger.info = MagicMock()
            mock_logger.error = MagicMock()
            mock_setup_logger.return_value = mock_logger

            MockAgent.return_value = mock_agent
            yield MockAgent, mock_setup_logger, mock_load_config, mock_logger

    def test_generate_config_flag(self, cli_runner):
        with patch('src.main.generate_default_config') as mock_gen_conf:
            result = cli_runner.invoke(main, ['--generate-config'])
            mock_gen_conf.assert_called_once()
            assert result.exit_code == 0

    def test_generate_project_flag(self, cli_runner):
        with patch('src.main.generate_default_project') as mock_gen_proj:
            result = cli_runner.invoke(main, ['--generate-project'])
            mock_gen_proj.assert_called_once()
            assert result.exit_code == 0

    def test_main_with_config_file(self, cli_runner, mock_dependencies):
        MockAgent, mock_setup_logger, mock_load_config, mock_logger = mock_dependencies

        mock_load_config.return_value = {
            'agent': {'agent_id': 'custom_agent'},
            'logging': {'level': 'INFO', 'file': 'agent.log'}
        }

        config_path = os.path.abspath(
            'matlab_agent/config/config.yaml.template')
        result = cli_runner.invoke(main, ['-c', config_path])

        mock_load_config.assert_called_once_with(config_path)
        MockAgent.assert_called_once_with(
            'custom_agent',
            broker_type='rabbitmq',
            config_path=config_path)
        mock_agent = MockAgent.return_value
        mock_agent.start.assert_called_once()
        assert result.exit_code == 0

    def test_main_without_config_file(
            self, cli_runner, mock_dependencies, default_config):
        MockAgent, mock_setup_logger, mock_load_config, mock_logger = mock_dependencies

        with patch('os.path.exists', return_value=True):
            mock_load_config.return_value = default_config
            result = cli_runner.invoke(main, [])

            mock_load_config.assert_called_once_with('config.yaml')
            MockAgent.assert_called_once_with(
                'default_agent',
                broker_type='rabbitmq',
                config_path='config.yaml')
            mock_agent = MockAgent.return_value
            mock_agent.start.assert_called_once()
            assert result.exit_code == 0

    def test_main_without_config_file_missing_config(self, cli_runner):
        with patch('os.path.exists', return_value=False):
            result = cli_runner.invoke(main, [])
            assert "Error: Configuration file 'config.yaml' not found." in result.output
            assert result.exit_code == 0

    def test_main_keyboard_interrupt(self, cli_runner, default_config):
        with patch('src.main.MatlabAgent') as MockAgent, \
                patch('src.main.setup_logger') as mock_setup_logger, \
                patch('src.main.load_config') as mock_load_config, \
                patch('os.path.exists', return_value=True):

            mock_logger = MagicMock()
            mock_setup_logger.return_value = mock_logger
            mock_load_config.return_value = default_config

            mock_agent = MagicMock()
            mock_agent.start.side_effect = KeyboardInterrupt()
            MockAgent.return_value = mock_agent

            result = cli_runner.invoke(main, [])

            mock_agent.stop.assert_called_once()
            assert result.exit_code == 0

    def test_main_general_error(self, cli_runner, default_config):
        with patch('src.main.MatlabAgent') as MockAgent, \
                patch('src.main.setup_logger') as mock_setup_logger, \
                patch('src.main.load_config') as mock_load_config, \
                patch('os.path.exists', return_value=True):

            mock_logger = MagicMock()
            mock_setup_logger.return_value = mock_logger
            mock_load_config.return_value = default_config

            mock_agent = MagicMock()
            mock_agent.start.side_effect = Exception("Simulated failure")
            MockAgent.return_value = mock_agent

            result = cli_runner.invoke(main, [])

            mock_agent.stop.assert_called_once()
            assert result.exit_code == 0

    def test_invalid_log_level(self, cli_runner, invalid_log_config):
        with patch('src.main.MatlabAgent') as MockAgent, \
                patch('src.main.setup_logger') as mock_setup_logger, \
                patch('src.main.load_config') as mock_load_config, \
                patch('os.path.exists', return_value=True):

            mock_logger = MagicMock()
            mock_setup_logger.return_value = mock_logger
            mock_load_config.return_value = invalid_log_config

            mock_agent = MagicMock()
            MockAgent.return_value = mock_agent

            result = cli_runner.invoke(main, [])

            mock_setup_logger.assert_called_once_with(
                level=logging.INFO,
                log_file='app.log'
            )
            mock_agent.start.assert_called_once()
            assert result.exit_code == 0

    def test_run_agent_direct(self, mock_dependencies):
        MockAgent, mock_setup_logger, mock_load_config, mock_logger = mock_dependencies

        mock_load_config.return_value = {
            'agent': {'agent_id': 'custom_agent'},
            'logging': {'level': 'INFO', 'file': 'agent.log'}
        }

        run_agent('test_config.yml')

        mock_load_config.assert_called_once_with('test_config.yml')
        MockAgent.assert_called_once_with(
            'custom_agent',
            broker_type='rabbitmq',
            config_path='test_config.yml')
        mock_agent = MockAgent.return_value
        mock_agent.start.assert_called_once()
