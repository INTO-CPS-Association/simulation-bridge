import socket
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
import subprocess

import pytest

from src.streaming.streaming import (MatlabStreamingController,
                                     MatlabStreamingError, StreamingConnection,
                                     _handle_streaming_error,
                                     handle_streaming_simulation)


@pytest.fixture
def response_templates():
    """Fixture providing standardized response templates for tests."""
    return {
        'error': {
            'error_codes': {
                'bad_request': 400,
                'execution_error': 500,
                'missing_file': 404,
            },
            'include_stacktrace': False,
        },
    }


@pytest.fixture
def tcp_settings():
    """Fixture providing standardized TCP settings for tests."""
    return {'host': 'localhost', 'port': 1234}


@pytest.fixture
def patch_streaming_config(monkeypatch, response_templates, tcp_settings):
    """
    Fixture that patches the streaming configuration for test isolation.

    Args:
        monkeypatch: pytest's monkeypatch fixture
        response_templates: Response templates fixture
        tcp_settings: TCP settings fixture
    """
    monkeypatch.setattr(
        'src.streaming.streaming.response_templates',
        response_templates)
    monkeypatch.setattr('src.streaming.streaming.tcp_settings', tcp_settings)


@pytest.fixture
def mock_rabbit_client():
    """Fixture providing a mock RabbitMQ client."""
    return Mock()


@pytest.fixture
def mock_socket_pair():
    """
    Fixture that creates a pair of connected sockets for testing.

    Returns:
        tuple: (server_socket, client_socket, server_address)
    """
    # Create server socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', 0))  # Use random available port
    server.listen()
    addr = server.getsockname()

    # Create client socket
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(addr)

    # Accept connection on server side
    client_conn, _ = server.accept()

    yield server, client_conn, addr

    # Clean up
    client.close()
    client_conn.close()
    server.close()


@pytest.fixture
def streaming_connection():
    """
    Fixture providing a StreamingConnection instance.

    Returns:
        StreamingConnection: A connection instance
    """
    connection = StreamingConnection('127.0.0.1', 0)
    yield connection
    connection.close()


@pytest.fixture
def matlab_controller(monkeypatch, mock_rabbit_client):
    """
    Fixture providing a properly configured MatlabStreamingController.

    Args:
        monkeypatch: pytest's monkeypatch fixture
        mock_rabbit_client: Mock RabbitMQ client fixture

    Returns:
        MatlabStreamingController: A controller instance with mocked filesystem
    """
    # Mock filesystem checks to avoid actual file access
    monkeypatch.setattr('pathlib.Path.is_dir', lambda self: True)
    monkeypatch.setattr('pathlib.Path.exists', lambda self: True)

    controller = MatlabStreamingController(
        str(Path.cwd()), 'test_file.m', 'test_src', mock_rabbit_client
    )

    yield controller

    # Clean up
    controller.close()


def test_streaming_connection_lifecycle(streaming_connection):
    """
    Test the complete lifecycle of a StreamingConnection.

    Tests start_server, accept_connection, and close methods.
    """
    # Start the server
    streaming_connection.start_server()

    # Verify socket is created and listening
    assert streaming_connection.socket is not None

    # Mock socket operations
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', 0))
    server.listen()
    addr = server.getsockname()

    # Create client connection
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(addr)

    # Replace streaming connection's socket with our test socket
    streaming_connection.socket = server
    server.settimeout(1)

    # Accept connection
    streaming_connection.accept_connection(timeout=1)
    assert streaming_connection.connection is not None

    # Create and assign mock process
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    streaming_connection.matlab_process = fake_proc

    # Close connection
    streaming_connection.close()

    # Verify process was terminated
    fake_proc.terminate.assert_called_once()

    # Clean up sockets
    client.close()
    server.close()


@patch('src.streaming.streaming.subprocess.Popen')
def test_controller_start_failure(mock_popen, matlab_controller):
    """
    Test that controller.start raises MatlabStreamingError when Popen fails.
    """
    # Simulate Popen failure
    mock_popen.side_effect = Exception('Process start failed')

    # Verify exception is raised
    with pytest.raises(MatlabStreamingError):
        matlab_controller.start()


@patch('src.streaming.streaming.StreamingConnection.start_server')
@patch('src.streaming.streaming.subprocess.Popen')
def test_controller_start_success(
        mock_popen,
        mock_start_server,
        matlab_controller,
        mock_rabbit_client):
    """
    Test successful controller.start sends initial progress notification.
    """
    # Mock the MATLAB process
    fake_proc = MagicMock()
    mock_popen.return_value = fake_proc

    # Start the controller
    matlab_controller.start()

    # Verify progress message was sent
    mock_rabbit_client.send_result.assert_called_once()

    # Verify the keys in the sent progress message
    args = mock_rabbit_client.send_result.call_args[0]
    assert len(args) >= 2
    progress_data = args[1]
    assert 'progress' in progress_data


@patch('src.streaming.streaming.StreamingConnection.accept_connection')
def test_controller_run_success(
        mock_accept,
        matlab_controller,
        mock_rabbit_client):
    """
    Test controller.run processes JSON lines correctly.
    """
    # Create mock connection with predetermined response
    conn = StreamingConnection('host', 0)
    fake_sock = MagicMock()

    # Setup socket to return a valid JSON line and then EOF
    fake_sock.recv.side_effect = [
        b'{"progress": {"percentage": 10}, "data": {"x":1}}\n',
        b''
    ]
    conn.connection = fake_sock

    # Attach mock connection to controller
    matlab_controller.connection = conn

    # Run the controller with test input
    matlab_controller.run({'param': 'value'})

    # Verify result was sent
    assert mock_rabbit_client.send_result.call_count >= 1


def test_get_metadata(matlab_controller, monkeypatch):
    """
    Test get_metadata returns all expected monitoring keys.
    """
    # Create a fake process for monitoring
    class FakeProc:
        def __init__(self):
            self.pid = 1
            self._terminated = False

        def memory_info(self):
            return MagicMock(rss=1024 * 1024)  # 1 MB

        def cpu_percent(self):
            return 5.0  # 5% CPU usage

        def poll(self):
            """Simula il controllo del processo (None se attivo, codice di uscita se terminato)."""
            return None if not self._terminated else 0

        def terminate(self):
            """Simula la terminazione del processo."""
            self._terminated = True

        def wait(self, timeout=None):
            """Simula l'attesa di terminazione del processo."""
            if not self._terminated:
                raise subprocess.TimeoutExpired(cmd="matlab", timeout=timeout)

        def kill(self):
            """Simula un kill forzato del processo."""
            self._terminated = True

    # Patch psutil to use our fake process
    monkeypatch.setattr(
        'src.streaming.streaming.psutil.Process',
        lambda pid: FakeProc()
    )

    # Setup controller with process and start time
    matlab_controller.connection.matlab_process = FakeProc()
    matlab_controller.start_time = time.time() - 2  # 2 seconds ago

    # Get metadata
    metadata = matlab_controller.get_metadata()

    # Verify all expected keys are present
    assert 'execution_time' in metadata
    assert 'memory_usage' in metadata
    assert 'matlab_memory' in metadata
    assert 'matlab_cpu' in metadata

    # Verify values make sense
    assert metadata['execution_time'] >= 2.0  # At least 2 seconds
    assert metadata['matlab_memory'] == 1.0  # 1 MB
    assert metadata['matlab_cpu'] == 5.0  # 5%


def test_handle_streaming_error_bad_request(
        mock_rabbit_client, patch_streaming_config):
    """
    Test _handle_streaming_error sets HTTP 400 for bad requests.
    """
    # Simulate bad request error
    _handle_streaming_error(
        '',  # Empty data
        ValueError('Missing path/file configuration'),  # Value error
        'test_queue',  # Queue name
        mock_rabbit_client  # RabbitMQ client
    )

    # Get the sent error response
    sent_data = mock_rabbit_client.send_result.call_args[0][1]

    # Verify error code and type
    assert sent_data['error']['code'] == 400
    assert sent_data['error']['type'] == 'bad_request'


def test_handle_streaming_simulation_missing_fields(
        monkeypatch, mock_rabbit_client, patch_streaming_config):
    """
    Test handle_streaming_simulation reports error when required fields are missing.
    """
    # Mock MatlabStreamingController
    monkeypatch.setattr(
        'src.streaming.streaming.MatlabStreamingController',
        Mock()
    )

    # Call with incomplete data
    handle_streaming_simulation(
        {'simulation': {'foo': 'bar'}},  # Missing required fields
        'test_queue',
        mock_rabbit_client
    )

    # Get the sent error response
    sent_data = mock_rabbit_client.send_result.call_args[0][1]

    # Verify bad request error
    assert sent_data['error']['code'] == 400


def test_handle_streaming_simulation_success(
        monkeypatch,
        mock_rabbit_client,
        patch_streaming_config):
    """
    Test handle_streaming_simulation successful end-to-end path.
    """
    # Create mock controller
    fake_controller = Mock()

    # Mock controller creation to return our fake
    monkeypatch.setattr(
        'src.streaming.streaming.MatlabStreamingController',
        lambda path, f, s, r: fake_controller
    )

    # Complete simulation data with all required fields
    simulation_data = {
        'simulation': {
            'file': 'test_file.m',
            'inputs': {'param': 'value'}
        }
    }

    # Handle the simulation
    handle_streaming_simulation(
        simulation_data,
        'test_queue',
        mock_rabbit_client
    )

    # Verify controller methods were called
    fake_controller.start.assert_called_once()
    fake_controller.run.assert_called_once()

    # Verify result was sent (might be progress updates)
    assert mock_rabbit_client.send_result.called
