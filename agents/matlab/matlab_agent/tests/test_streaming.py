import socket
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from src.streaming.streaming import (MatlabStreamingController,
                                     MatlabStreamingError, StreamingConnection,
                                     _handle_streaming_error,
                                     handle_streaming_simulation)

# Sample configuration for testing
response_templates = {
    'error': {
        'error_codes': {
            'bad_request': 400,
            'execution_error': 500,
            'missing_file': 404,
        },
        'include_stacktrace': False,
    },
}


@pytest.fixture(autouse=True)
def patch_config(monkeypatch):
    """
    Patch the configuration and templates for isolation.
    """
    monkeypatch.setattr(
        'src.streaming.streaming.response_templates', response_templates)
    monkeypatch.setattr('src.streaming.streaming.tcp_settings', {
                        'host': 'localhost', 'port': 1234})


def test_streaming_connection_start_and_close(tmp_path):
    """
    Test StreamingConnection start_server, accept_connection, and close.
    """
    conn = StreamingConnection('127.0.0.1', 0)
    conn.start_server()
    # Ensure socket is listening
    assert conn.socket is not None
    # Mock accept: use a pair of connected sockets
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', 0))
    server.listen()
    addr = server.getsockname()
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(addr)
    conn.socket = server
    server.settimeout(1)
    conn.accept_connection(timeout=1)
    assert conn.connection is not None
    # Assign fake process and test close
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    conn.matlab_process = fake_proc
    conn.close()
    fake_proc.terminate.assert_called_once()
    # Closing again no error
    conn.close()


@patch('src.streaming.streaming.subprocess.Popen')
@patch('pathlib.Path.exists')
@patch('pathlib.Path.is_dir')
def test_controller_start_failure(mock_is_dir, mock_exists, mock_popen):
    """
    Test che controller.start sollevi un MatlabStreamingError in caso di fallimento di Popen.
    """
    # Mockiamo i metodi del filesystem per evitare il FileNotFoundError
    mock_is_dir.return_value = True  # Mock che il percorso è una directory
    # Mock che il file esiste (così la validazione non fallisce)
    mock_exists.return_value = True

    # Simuliamo il fallimento di Popen sollevando un'eccezione
    mock_popen.side_effect = Exception('fail')

    # Creiamo l'istanza del controller
    controller = MatlabStreamingController(
        str(Path.cwd()), 'file.m', 'src', MagicMock()
    )

    # Verifichiamo che venga sollevato un MatlabStreamingError quando
    # chiamiamo start
    with pytest.raises(MatlabStreamingError):
        controller.start()


@patch('src.streaming.streaming.StreamingConnection.start_server')
@patch('src.streaming.streaming.subprocess.Popen')
@patch('pathlib.Path.exists')
@patch('pathlib.Path.is_dir')
def test_controller_start_success(
        mock_is_dir,
        mock_exists,
        mock_popen,
        mock_start_server):
    """
    Test successful controller.start sends initial progress (without aprire realmente la socket).
    """
    # Mock filesystem checks
    mock_is_dir.return_value = True
    mock_exists.return_value = True

    # Mock del processo MATLAB
    fake_proc = MagicMock()
    mock_popen.return_value = fake_proc

    rabbit = Mock()
    controller = MatlabStreamingController(
        str(Path.cwd()), 'file.m', 'src', rabbit
    )

    # Ora start_server è un no-op grazie al patch
    controller.start()

    # Verifichiamo che abbiamo inviato esattamente un messaggio di progresso
    rabbit.send_result.assert_called_once()


@patch('src.streaming.streaming.StreamingConnection.accept_connection')
@patch('pathlib.Path.exists')
@patch('pathlib.Path.is_dir')
def test_controller_run_success(mock_is_dir, mock_exists, mock_accept):
    """
    Test controller.run processes JSON lines correctly.
    """
    # Mock filesystem checks
    mock_is_dir.return_value = True
    mock_exists.return_value = True

    # Mock connection and data
    conn = StreamingConnection('host', 0)
    fake_sock = MagicMock()
    fake_sock.recv.side_effect = [
        b'{"progress": {"percentage": 10}, "data": {"x":1}}\n', b'']
    conn.connection = fake_sock

    rabbit = Mock()
    controller = MatlabStreamingController(
        str(Path.cwd()), 'file.m', 'src', rabbit
    )
    controller.connection = conn
    controller.run({'a': 1})
    assert rabbit.send_result.call_count >= 1


def test_get_metadata(monkeypatch):
    """
    Test get_metadata returns expected keys.
    """
    monkeypatch.setattr('pathlib.Path.is_dir', lambda self: True)
    monkeypatch.setattr('pathlib.Path.exists', lambda self: True)
    controller = MatlabStreamingController(
        str(Path.cwd()), 'file.m', 'src', Mock()
    )
    # Patch psutil to control memory/cpu values

    class FakeProc:
        def __init__(self):
            self.pid = 1

        def memory_info(self):
            return MagicMock(rss=1024 * 1024)

        def cpu_percent(self):
            return 5.0
    monkeypatch.setattr(
        'src.streaming.streaming.psutil.Process', lambda pid: FakeProc())
    controller.connection.matlab_process = FakeProc()
    controller.start_time = time.time() - 2
    meta = controller.get_metadata()
    assert 'execution_time' in meta
    assert 'memory_usage' in meta
    assert 'matlab_memory' in meta
    assert 'matlab_cpu' in meta


def test_handle_streaming_error_bad_request():
    """
    Test _handle_streaming_error sets HTTP 400 for bad requests.
    """
    rabbit = Mock()
    _handle_streaming_error('', ValueError(
        'Missing path/file configuration'), 'q', rabbit)
    sent = rabbit.send_result.call_args[0][1]
    assert sent['error']['code'] == 400
    assert sent['error']['type'] == 'bad_request'


def test_handle_streaming_simulation_missing_fields(monkeypatch):
    """
    Test handle_streaming_simulation without required fields.
    """
    monkeypatch.setattr(
        'src.streaming.streaming.MatlabStreamingController', Mock())
    rabbit = Mock()
    handle_streaming_simulation({'simulation': {'foo': 'bar'}}, 'q', rabbit)
    sent = rabbit.send_result.call_args[0][1]
    assert sent['error']['code'] == 400


def test_handle_streaming_simulation_success(monkeypatch):
    """
    Test handle_streaming_simulation end-to-end success path.
    """
    fake_ctrl = Mock()
    monkeypatch.setattr(
        'src.streaming.streaming.MatlabStreamingController',
        lambda path,
        f,
        s,
        r: fake_ctrl)
    rabbit = Mock()
    data = {'simulation': {'file': 'f.m', 'inputs': {}}}
    handle_streaming_simulation(data, 'q', rabbit)
    # Ensure start, run, send_result called
    fake_ctrl.start.assert_called_once()
    fake_ctrl.run.assert_called_once()
    rabbit.send_result.assert_called()
