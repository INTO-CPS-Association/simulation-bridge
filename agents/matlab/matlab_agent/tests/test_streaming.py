# Import necessary modules and dependencies
import pytest
from unittest.mock import Mock, MagicMock, patch, call
import socket
import subprocess
import json
from pathlib import Path
from datetime import datetime
import sys
from src.streaming.streaming import (
    MatlabStreamingController,
    create_response,
    handle_streaming_simulation,
    MatlabStreamingError
)

# Define pytest fixtures for reusable mock configurations
@pytest.fixture
def mock_config():
    # Mock configuration for response templates and TCP settings
    return {
        'response_templates': {
            'success': {
                'status': 'completed',
                'include_metadata': True
            },
            'error': {
                'status': 'error',
                'error_codes': {
                    'invalid_config': 400,
                    'socket_creation_failure': 500
                }
            },
            'streaming': {
                'status': 'streaming'
            }
        },
        'tcp': {
            'host': 'localhost',
            'port': 5678
        }
    }

@pytest.fixture
def mock_rabbitmq():
    # Mock RabbitMQ instance
    return Mock()

@pytest.fixture
def sample_sim_data():
    # Sample simulation data for testing
    return {
        'simulation': {
            'file': 'simulation_streaming.m',
            'inputs': {
                'num_agents': 8,
                'max_steps': 200,
                'avoidance_threshold': 1,
                'show_agent_index': 1,
                'use_gui': True
            }
        }
    }

# Tests for MatlabStreamingController initialization
@patch('subprocess.Popen')
@patch('socket.socket')
def test_controller_init_valid(mock_socket, mock_popen, mock_config):
    # Test valid initialization of MatlabStreamingController
    controller = MatlabStreamingController(
        '/Users/marcomelloni/Desktop/AU_University/simulation-bridge/agents/matlab/matlab_agent/docs/examples',
        'simulation_streaming.m',
        'test_source',
        Mock()
    )
    assert controller.sim_path == Path('/Users/marcomelloni/Desktop/AU_University/simulation-bridge/agents/matlab/matlab_agent/docs/examples').resolve()

def test_controller_init_invalid_path():
    # Test initialization with an invalid simulation path
    with patch('pathlib.Path.exists', return_value=False):
        with pytest.raises(FileNotFoundError):
            MatlabStreamingController(
                '/invalid/path',
                'simulation_streaming.m',
                'source',
                Mock()
            )

# Tests for starting the MatlabStreamingController
@patch('subprocess.Popen')
@patch('socket.socket')
def test_controller_start_success(mock_socket, mock_popen, mock_config):
    # Test successful start of the controller
    mock_sock_instance = MagicMock()
    mock_socket.return_value = mock_sock_instance
    
    controller = MatlabStreamingController(
        '/Users/marcomelloni/Desktop/AU_University/simulation-bridge/agents/matlab/matlab_agent/docs/examples',
        'simulation_streaming.m',
        'source',
        Mock()
    )
    controller.start()
    
    mock_sock_instance.bind.assert_called_with(('localhost', 5678))
    mock_sock_instance.listen.assert_called_once()

@patch('subprocess.Popen')
def test_controller_start_failure(mock_popen):
    # Test failure during controller start due to MATLAB error
    mock_popen.side_effect = Exception("MATLAB failed")
    controller = MatlabStreamingController(
        '/Users/marcomelloni/Desktop/AU_University/simulation-bridge/agents/matlab/matlab_agent/docs/examples',
        'simulation_streaming.m',
        'source',
        Mock()
    )
    with pytest.raises(MatlabStreamingError):
        controller.start()

# Tests for running the MatlabStreamingController
@patch('socket.socket')
def test_controller_run_success(mock_socket, mock_rabbitmq):
    # Test successful execution of the controller's run method
    mock_conn = MagicMock()
    mock_socket_instance = MagicMock()
    mock_socket_instance.accept.return_value = (mock_conn, ('localhost', 12345))
    mock_socket.return_value = mock_socket_instance
    
    mock_conn.recv.side_effect = [b'{"data": 42}\n', b'']
    
    controller = MatlabStreamingController(
        '/Users/marcomelloni/Desktop/AU_University/simulation-bridge/agents/matlab/matlab_agent/docs/examples',
        'simulation_streaming.m',
        'source',
        mock_rabbitmq
    )
    controller.socket = mock_socket_instance
    controller.run({'num_agents': 8, 'max_steps': 200})
    
    # Verify data sent to RabbitMQ
    assert mock_rabbitmq.send_result.call_count >= 1

# Tests for cleanup during controller close
def test_controller_close_cleanup():
    # Test proper cleanup of resources during controller close
    mock_process = MagicMock()
    mock_socket = MagicMock()
    
    controller = MatlabStreamingController(
        '/Users/marcomelloni/Desktop/AU_University/simulation-bridge/agents/matlab/matlab_agent/docs/examples',
        'simulation_streaming.m',
        'source',
        Mock()
    )
    controller.matlab_process = mock_process
    controller.socket = mock_socket
    controller.connection = MagicMock()
    
    # Simulate a running process
    mock_process.poll.return_value = None
    
    controller.close()
    
    mock_process.terminate.assert_called_once()  # Ensure terminate is called
    mock_socket.close.assert_called_once()  # Ensure socket is closed


# Tests for handling streaming simulation
@patch('src.streaming.streaming.MatlabStreamingController')
def test_handle_streaming_success(MockController, mock_rabbitmq, sample_sim_data):
    # Test successful handling of streaming simulation
    mock_instance = Mock()
    MockController.return_value = mock_instance
    
    handle_streaming_simulation(
        {'simulation': sample_sim_data['simulation']},
        'test_queue',
        mock_rabbitmq
    )
    
    MockController.assert_called_with(
        '/Users/marcomelloni/Desktop/AU_University/simulation-bridge/agents/matlab/matlab_agent/docs/examples',
        'simulation_streaming.m',
        'test_queue',
        mock_rabbitmq
    )
    


@patch('src.streaming.streaming.MatlabStreamingController')
def test_handle_streaming_missing_fields(MockController, mock_rabbitmq):
    # Test handling of streaming simulation with missing fields
    invalid_data = {'simulation': {'name': 'test'}}
    
    handle_streaming_simulation(
        invalid_data,
        'test_queue',
        mock_rabbitmq
    )
    
    sent_response = mock_rabbitmq.send_result.call_args[0][1]
    assert sent_response['error']['code'] == 400

@patch('src.streaming.streaming.MatlabStreamingController')
def test_handle_streaming_runtime_error(MockController, mock_rabbitmq, sample_sim_data):
    # Test handling of runtime error during streaming simulation
    mock_instance = Mock()
    mock_instance.start.side_effect = MatlabStreamingError("Socket error")
    MockController.return_value = mock_instance
    
    handle_streaming_simulation(
        {'simulation': sample_sim_data['simulation']},
        'test_queue',
        mock_rabbitmq
    )
    
    sent_response = mock_rabbitmq.send_result.call_args[0][1]
    assert sent_response['status'] == 'error'

# Tests for TCP communication
@patch('socket.socket')
def test_tcp_communication(mock_socket, mock_rabbitmq):
    # Test TCP communication during simulation
    mock_conn = MagicMock()
    mock_sock_instance = MagicMock()
    mock_sock_instance.accept.return_value = (mock_conn, ('localhost', 12345))
    
    test_data = [b'{"temp": 37.5}\n', b'{"temp": 38.0}\n']
    mock_conn.recv.side_effect = test_data + [b'']
    
    controller = MatlabStreamingController(
        '/Users/marcomelloni/Desktop/AU_University/simulation-bridge/agents/matlab/matlab_agent/docs/examples',
        'simulation_streaming.m',
        'source',
        mock_rabbitmq
    )
    controller.socket = mock_sock_instance
    controller.run({'num_agents': 8, 'max_steps': 200})
    
    # Verify correct number of data messages sent
    assert mock_rabbitmq.send_result.call_count == len(test_data)

# Tests for error handling
def test_matlab_process_metadata():
    # Test retrieval of MATLAB process metadata
    controller = MatlabStreamingController(
        '/Users/marcomelloni/Desktop/AU_University/simulation-bridge/agents/matlab/matlab_agent/docs/examples',
        'simulation_streaming.m',
        'source',
        Mock()
    )
    controller.matlab_process = MagicMock()
    controller.matlab_process.poll.return_value = None
    
    metadata = controller.get_metadata()
    assert 'matlab_process_running' in metadata
    assert metadata['matlab_process_running'] is True

# Tests for forced termination of MATLAB process
def test_force_kill_matlab():
    # Test forced termination of MATLAB process on timeout
    mock_process = MagicMock()
    mock_process.poll.return_value = None
    mock_process.wait.side_effect = subprocess.TimeoutExpired("", 10)
    
    controller = MatlabStreamingController(
        '/Users/marcomelloni/Desktop/AU_University/simulation-bridge/agents/matlab/matlab_agent/docs/examples',
        'simulation_streaming.m',
        'source',
        Mock()
    )
    controller.matlab_process = mock_process
    controller.close()
    
    mock_process.kill.assert_called_once()
