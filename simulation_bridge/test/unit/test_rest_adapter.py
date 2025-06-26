"""
simulation_bridge/test/unit/test_rest_adapter.py
"""
# pylint: disable=protected-access,unused-argument,redefined-outer-name
import asyncio
import json
import warnings

from unittest.mock import MagicMock, AsyncMock
import pytest

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
