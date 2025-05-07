import logging
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

# Import the main function from the source module
from src.main import main

### Fixtures ###

@pytest.fixture
def config_data():
    # Returns a sample configuration with logging and agent details
    return {
        'logging': {'level': 'DEBUG', 'file': 'debug.log'},
        'agent': {'agent_id': 'test_logger'}
    }

@pytest.fixture
def default_config():
    # Returns the default configuration with logging and agent details
    return {
        'logging': {'level': 'INFO', 'file': 'app.log'},
        'agent': {'agent_id': 'default_agent'}
    }

@pytest.fixture
def missing_agent_config():
    # Returns a configuration missing the agent_id
    return {
        'logging': {'level': 'INFO', 'file': 'app.log'},
        'agent': {}  # Missing agent_id
    }

@pytest.fixture
def mock_agent():
    # Creates a mock agent with start and stop methods
    agent = MagicMock()
    agent.start = MagicMock()
    agent.stop = MagicMock()
    return agent

### Tests ###

@patch('src.main.MatlabAgent')
@patch('src.main.setup_logger')
@patch('src.main.load_config')
def test_main_with_custom_agent_id(mock_load_config, mock_setup_logger, MockAgent, default_config, mock_agent):
    # Tests main function with a custom agent_id passed via CLI
    mock_load_config.return_value = default_config
    MockAgent.return_value = mock_agent

    runner = CliRunner()
    result = runner.invoke(main, ['custom_agent'])

    MockAgent.assert_called_once_with('custom_agent')
    mock_agent.start.assert_called_once()
    assert result.exit_code == 0

@patch('src.main.MatlabAgent')
@patch('src.main.setup_logger')
@patch('src.main.load_config')
def test_main_default_agent_id(mock_load_config, mock_setup_logger, MockAgent, default_config, mock_agent):
    # Tests main function using default agent_id from configuration when not passed via CLI
    mock_load_config.return_value = {'logging': default_config['logging'],
                                     'agent': {'agent_id': 'config_agent'}}
    MockAgent.return_value = mock_agent

    runner = CliRunner()
    result = runner.invoke(main, [])

    MockAgent.assert_called_once_with('config_agent')
    mock_agent.start.assert_called_once()
    assert result.exit_code == 0

@patch('src.main.MatlabAgent')
@patch('src.main.setup_logger')
@patch('src.main.load_config')
def test_main_keyboard_interrupt(mock_load_config, mock_setup_logger, MockAgent, default_config, mock_agent):
    # Verifies that KeyboardInterrupt triggers stop() and exits with code 0
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
def test_main_general_error(mock_load_config, mock_setup_logger, MockAgent, default_config, mock_agent):
    # Verifies that a generic exception triggers stop() but exits with code 0
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
def test_invalid_log_level(mock_load_config, mock_setup_logger, MockAgent, missing_agent_config, mock_agent):
    # Tests fallback to INFO log level when an invalid level is provided
    cfg = {'logging': {'level': 'INVALID', 'file': 'app.log'},
           'agent': {'agent_id': 'default'}}
    mock_load_config.return_value = cfg
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
def test_missing_agent_id(mock_load_config, mock_setup_logger, MockAgent, missing_agent_config):
    # Tests error handling when agent_id is missing, ensuring exit_code != 0
    mock_load_config.return_value = missing_agent_config
    runner = CliRunner()
    result = runner.invoke(main, [])

    assert result.exit_code != 0
