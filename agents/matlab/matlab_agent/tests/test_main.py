import logging
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
import os

# Import the main function dalla tua entry-point
from src.main import main

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
def invalid_log_config():
    return {
        'logging': {'level': 'INVALID', 'file': 'app.log'},
        'agent': {'agent_id': 'agent_x'}
    }

@pytest.fixture
def missing_agent_config():
    return {
        'logging': {'level': 'INFO', 'file': 'app.log'},
        'agent': {}  # manca agent_id
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
def test_main_with_config_file(mock_load_config, mock_setup_logger, MockAgent, custom_config, mock_agent):
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
def test_main_without_config_file(mock_load_config, mock_setup_logger, MockAgent, default_config, mock_agent):
    # Se non passo -c, deve chiamare load_config con None
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
def test_main_keyboard_interrupt(mock_load_config, mock_setup_logger, MockAgent, default_config, mock_agent):
    # Simulo KeyboardInterrupt in start()
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
    # Simulo errore generico in start()
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
def test_invalid_log_level(mock_load_config, mock_setup_logger, MockAgent, invalid_log_config, mock_agent):
    # Se il livello di log è invalido, deve ricadere su INFO
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
def test_missing_agent_id(mock_load_config, mock_setup_logger, MockAgent, missing_agent_config):
    # Se manca agent_id nella config, lancia KeyError => exit_code != 0
    mock_load_config.return_value = missing_agent_config

    runner = CliRunner()
    result = runner.invoke(main, [])

    assert result.exit_code != 0
