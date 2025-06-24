"""
simulation_bridge/test/unit/test_rest_adapter.py
"""
# pylint: disable=protected-access,unused-argument,redefined-outer-name
import asyncio
import json
import warnings

from unittest.mock import MagicMock, AsyncMock
import pytest
from quart import Response

from simulation_bridge.src.protocol_adapters.rest import rest_adapter

warnings.filterwarnings("ignore", category=RuntimeWarning)


@pytest.fixture
def config_mock():
    """Mock REST config dictionary."""
    return {
        'host': '127.0.0.1',
        'port': 5000,
        'endpoint': '/stream',
        'certfile': None,
        'keyfile': None
    }


@pytest.fixture
def config_manager_mock(config_mock):
    """Mock config manager returning REST config."""
    mock = MagicMock()
    mock.get_rest_config.return_value = config_mock
    return mock


@pytest.fixture
def adapter(config_manager_mock):
    """Create RESTAdapter instance with mock config manager."""
    return rest_adapter.RESTAdapter(config_manager_mock)


@pytest.mark.asyncio
async def test_handle_streaming_message_valid_and_invalid(monkeypatch, adapter):
    """Test streaming message handler with valid and invalid JSON."""

    class DummyRequest:  # pylint: disable=too-few-public-methods
        """Dummy request object for valid JSON."""
        headers = {'content-type': 'application/json'}

        async def get_data(self):
            """Return valid JSON data."""
            return b'{"simulation": {"client_id": "prod1", "simulator": "sim1"}}'

    monkeypatch.setattr(rest_adapter, 'request', DummyRequest())

    signal_mock = MagicMock()
    monkeypatch.setattr(rest_adapter, 'signal', lambda name: signal_mock)

    response = await adapter._handle_streaming_message()
    assert isinstance(response, Response)
    assert response.status_code == 200
    assert response.content_type == 'application/x-ndjson'
    assert 'prod1' in adapter._active_streams
    assert isinstance(adapter._active_streams['prod1'], asyncio.Queue)
    signal_mock.send.assert_called_once()

    class BadRequest:  # pylint: disable=too-few-public-methods
        """Dummy request object for invalid JSON."""
        headers = {'content-type': 'application/json'}

        async def get_data(self):
            """Return invalid JSON data."""
            return b'{"simulation": invalid json'

    monkeypatch.setattr(rest_adapter, 'request', BadRequest())
    response = await adapter._handle_streaming_message()
    assert response.status_code == 400
    data = (await response.get_data()).decode()
    assert 'error' in data


@pytest.mark.asyncio
async def test_generate_response_yields_and_cleans_queue(adapter):
    """Test response generator yields initial status and queued results."""

    queue = asyncio.Queue()
    producer = "prod_test"
    adapter._active_streams[producer] = queue

    await queue.put({"result": "ok"})

    gen = adapter._generate_response(producer, queue)
    first = await gen.asend(None)
    assert json.loads(first)['status'] == 'processing'

    second = await gen.asend(None)
    assert json.loads(second)['result'] == 'ok'

    await gen.aclose()
    assert producer not in adapter._active_streams


@pytest.mark.asyncio
async def test_send_result_puts_message_in_queue(adapter):
    """Test send_result puts a message into the correct queue."""

    queue = asyncio.Queue()
    producer = 'client1'
    adapter._active_streams[producer] = queue

    result = {'data': 123}
    await adapter.send_result(producer, result)
    received = await queue.get()
    assert received == result


@pytest.mark.asyncio
async def test_send_result_warns_when_no_active_stream(adapter, caplog):
    """Test send_result logs warning if no active stream found."""

    await adapter.send_result('nonexistent', {'x': 1})
    assert 'No active stream found' in caplog.text


def test_start_calls_asyncio_run(monkeypatch, adapter):
    """Test start calls asyncio.run and sets running flag."""

    async def fake_start():
        return None

    monkeypatch.setattr(adapter, '_start_server', fake_start)
    monkeypatch.setattr('asyncio.run', lambda coro: asyncio.get_event_loop(
    ).run_until_complete(coro))  # pylint: disable=line-too-long
    adapter._running = False
    adapter.start()
    assert adapter._running is True


@pytest.mark.asyncio
async def test_publish_result_message_rest_calls_send_result_sync(
        monkeypatch, adapter):
    """Test that publish_result_message_rest calls send_result_sync correctly."""

    monkeypatch.setattr(adapter, 'send_result_sync', AsyncMock())
    msg = {'destinations': ['dest1']}
    adapter.publish_result_message_rest(None, message=msg)
    adapter.send_result_sync.assert_called_once_with('dest1', msg)


def test_start_creates_server_task(monkeypatch, adapter):
    """Test that start sets running and schedules _start_server as asyncio task."""

    async def fake_start_server():
        return None

    monkeypatch.setattr(adapter, '_start_server', fake_start_server)
    adapter._running = False

    # Patch get_event_loop to ensure we have a loop
    loop = asyncio.new_event_loop()
    monkeypatch.setattr(asyncio, 'get_event_loop', lambda: loop)

    adapter.start()

    assert adapter._running is True
    assert adapter._server_task is not None
    assert not adapter._server_task.done()


def test_stop_cancels_server_task(monkeypatch, adapter):
    adapter._running = True
    mock_task = MagicMock()
    adapter._server_task = mock_task

    adapter.stop()

    assert adapter._running is False
    mock_task.cancel.assert_called_once()
