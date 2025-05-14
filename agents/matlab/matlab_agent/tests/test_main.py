import logging
from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner
# Import the main function from the entry-point
from src.main import main, run_single_agent

### Fixtures ###


@pytest.fixture
def default_config():
    return {
        'logging': {'level': 'INFO', 'file': 'app.log'},
        'agent': {'agent_id': 'default_agent'}
    }


@pytest.fixture
def custom_config():
    return {
        'logging': {'level': 'DEBUG', 'file': 'debug.log'},
        'agent': {'agent_id': 'custom_agent'}
    }


@pytest.fixture
def second_config():
    return {
        'logging': {'level': 'INFO', 'file': 'agent2.log'},
        'agent': {'agent_id': 'second_agent'}
    }


@pytest.fixture
def invalid_log_config():
    return {
        'logging': {'level': 'INVALID', 'file': 'app.log'},
        'agent': {'agent_id': 'agent_x'}
    }


@pytest.fixture
def missing_agent_config():
    return {
        'logging': {'level': 'INFO', 'file': 'app.log'},
        'agent': {}  # missing agent_id
    }


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.start = MagicMock()
    agent.stop = MagicMock()
    return agent

### Tests ###


@patch('src.main.MatlabAgent')
@patch('src.main.setup_logger')
@patch('src.main.load_config')
def test_main_with_config_file(
        mock_load_config,
        mock_setup_logger,
        MockAgent,
        custom_config,
        mock_agent):
    mock_load_config.return_value = custom_config
    MockAgent.return_value = mock_agent

    abs_path = '/Users/marcomelloni/Desktop/AU_University/simulation-bridge/agents/matlab/matlab_agent/config'
    runner = CliRunner()
    result = runner.invoke(main, ['-c', abs_path])

    mock_load_config.assert_called_once_with(abs_path)
    MockAgent.assert_called_once_with('custom_agent')
    mock_agent.start.assert_called_once()
    assert result.exit_code == 0


@patch('src.main.MatlabAgent')
@patch('src.main.setup_logger')
@patch('src.main.load_config')
def test_main_without_config_file(
        mock_load_config,
        mock_setup_logger,
        MockAgent,
        default_config,
        mock_agent):
    # Should call load_config with None if -c is not provided
    mock_load_config.return_value = default_config
    MockAgent.return_value = mock_agent

    runner = CliRunner()
    result = runner.invoke(main, [])

    mock_load_config.assert_called_once_with(None)
    MockAgent.assert_called_once_with('default_agent')
    mock_agent.start.assert_called_once()
    assert result.exit_code == 0


@patch('src.main.MatlabAgent')
@patch('src.main.setup_logger')
@patch('src.main.load_config')
def test_main_keyboard_interrupt(
        mock_load_config,
        mock_setup_logger,
        MockAgent,
        default_config,
        mock_agent):
    # Simulate KeyboardInterrupt in start()
    mock_load_config.return_value = default_config
    mock_agent.start.side_effect = KeyboardInterrupt()
    MockAgent.return_value = mock_agent

    runner = CliRunner()
    result = runner.invoke(main, [])

    mock_agent.stop.assert_called_once()
    assert result.exit_code == 0


@patch('src.main.MatlabAgent')
@patch('src.main.setup_logger')
@patch('src.main.load_config')
def test_main_general_error(
        mock_load_config,
        mock_setup_logger,
        MockAgent,
        default_config,
        mock_agent):
    # Simulate general error in start()
    mock_load_config.return_value = default_config
    mock_agent.start.side_effect = Exception("Simulated failure")
    MockAgent.return_value = mock_agent

    runner = CliRunner()
    result = runner.invoke(main, [])

    mock_agent.stop.assert_called_once()
    assert result.exit_code == 0


@patch('src.main.MatlabAgent')
@patch('src.main.setup_logger')
@patch('src.main.load_config')
def test_invalid_log_level(
        mock_load_config,
        mock_setup_logger,
        MockAgent,
        invalid_log_config,
        mock_agent):
    # If log level is invalid, should fall back to INFO
    mock_load_config.return_value = invalid_log_config
    MockAgent.return_value = mock_agent

    runner = CliRunner()
    result = runner.invoke(main, [])

    mock_setup_logger.assert_called_once_with(
        level=logging.INFO,
        log_file='app.log'
    )
    assert result.exit_code == 0


@patch('src.main.MatlabAgent')
@patch('src.main.setup_logger')
@patch('src.main.load_config')
def test_missing_agent_id(
        mock_load_config,
        mock_setup_logger,
        MockAgent,
        missing_agent_config):
    # If agent_id is missing in config, raises KeyError => exit_code != 0
    mock_load_config.return_value = missing_agent_config

    runner = CliRunner()
    result = runner.invoke(main, [])

    assert result.exit_code != 0

# New tests for multiagent mode and other uncovered lines


@patch('src.main.MatlabAgent')
@patch('src.main.setup_logger')
@patch('src.main.load_config')
def test_run_single_agent_direct(
        mock_load_config,
        mock_setup_logger,
        MockAgent,
        custom_config,
        mock_agent):
    """Test the run_single_agent function directly."""
    mock_load_config.return_value = custom_config
    MockAgent.return_value = mock_agent

    run_single_agent('test_config.yml')

    mock_load_config.assert_called_once_with('test_config.yml')
    MockAgent.assert_called_once_with('custom_agent')
    mock_agent.start.assert_called_once()
