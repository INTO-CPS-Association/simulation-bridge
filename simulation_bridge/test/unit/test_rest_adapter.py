"""
simulation_bridge/test/unit/test_rest_adapter.py
"""
# pylint: disable=protected-access,unused-argument,redefined-outer-name
import asyncio
import base64
import json
import time
import warnings

import jwt as pyjwt
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from simulation_bridge.src.protocol_adapters.rest import rest_adapter

warnings.filterwarnings("ignore", category=RuntimeWarning)

_JWT_SECRET = "test-secret"
_JWT_ALGORITHM = "HS256"


def _make_jwt(overrides=None, secret=_JWT_SECRET, algorithm=_JWT_ALGORITHM):
    """Build a valid signed JWT for testing."""
    now = int(time.time())
    payload = {"sub": "user1", "iss": "test-iss",
               "exp": now + 3600, "iat": now}
    if overrides:
        payload.update(overrides)
    return pyjwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture
def config_mock():
    """Mock REST config dictionary."""
    return {
        'host': '127.0.0.1',
        'port': 5000,
        'endpoint': '/stream',
        'certfile': None,
        'keyfile': None,
        'jwt': {
            'secret': _JWT_SECRET,
            'algorithm': _JWT_ALGORITHM,
            'max_token_age_seconds': 3600,
        }
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
    loop = asyncio.new_event_loop()
    monkeypatch.setattr('asyncio.run', loop.run_until_complete)
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


# ---------------------------------------------------------------------------
# _extract_jwt_payload
# ---------------------------------------------------------------------------

def test_extract_jwt_payload_missing_bearer(adapter):
    """Raise ValueError when Authorization header has no Bearer token."""
    mock_req = MagicMock()
    mock_req.headers.get.return_value = "Basic abc123"
    with pytest.raises(ValueError, match="Missing Bearer token"):
        adapter._extract_jwt_payload(mock_req)


def test_extract_jwt_payload_valid(adapter):
    """Valid Bearer token is verified and payload returned."""
    token = _make_jwt()
    mock_req = MagicMock()
    mock_req.headers.get.return_value = f"Bearer {token}"
    payload = adapter._extract_jwt_payload(mock_req)
    assert payload["sub"] == "user1"


# ---------------------------------------------------------------------------
# _parse_message
# ---------------------------------------------------------------------------

def test_parse_message_yaml_content_type(adapter):
    """YAML content type is parsed correctly."""
    body = b"key: value"
    result = adapter._parse_message(body, "application/yaml")
    assert result == {"key": "value"}


def test_parse_message_json_content_type(adapter):
    """JSON content type is parsed correctly."""
    body = b'{"x": 1}'
    result = adapter._parse_message(body, "application/json")
    assert result == {"x": 1}


def test_parse_message_fallback_yaml(adapter):
    """Fallback: parses YAML when content type is unknown."""
    body = b"foo: bar"
    result = adapter._parse_message(body, "text/plain")
    assert result == {"foo": "bar"}


def test_parse_message_fallback_json(adapter):
    """Fallback: parses JSON when YAML fails."""
    body = b'{"a": 2}'
    result = adapter._parse_message(body, "text/plain")
    assert result == {"a": 2}


def test_parse_message_fallback_raw(adapter):
    """Fallback: returns raw content when YAML and JSON fail."""
    with patch("yaml.safe_load", side_effect=Exception("yaml fail")), \
            patch("json.loads", side_effect=Exception("json fail")):
        body = b"raw content"
        result = adapter._parse_message(body, "text/plain")
    assert result.get("raw_message") is True


# ---------------------------------------------------------------------------
# _generate_response: timeout and error branches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_response_timeout(adapter):
    """Stream yields a timeout message when queue.get times out."""
    producer = "prod_timeout"
    queue = asyncio.Queue()
    adapter._active_streams[producer] = queue

    async def fast_timeout(coro, timeout):  # pylint: disable=unused-argument
        coro.close()
        raise asyncio.TimeoutError()

    gen = adapter._generate_response(producer, queue)
    first = await gen.asend(None)
    assert "processing" in first

    with patch("asyncio.wait_for", fast_timeout):
        second = await gen.asend(None)
    assert "timeout" in second
    await gen.aclose()
    assert producer not in adapter._active_streams


@pytest.mark.asyncio
async def test_generate_response_error(adapter):
    """Stream yields an error message when queue.get raises."""
    producer = "prod_error"
    queue = asyncio.Queue()
    adapter._active_streams[producer] = queue

    async def raising_wait_for(coro, timeout):  # pylint: disable=unused-argument
        coro.close()
        raise RuntimeError("boom")

    gen = adapter._generate_response(producer, queue)
    first = await gen.asend(None)
    assert "processing" in first

    with patch("asyncio.wait_for", raising_wait_for):
        second = await gen.asend(None)
    assert "error" in second
    await gen.aclose()
    assert producer not in adapter._active_streams


# ---------------------------------------------------------------------------
# send_result_sync
# ---------------------------------------------------------------------------

def test_send_result_sync_no_active_stream(adapter, caplog):
    """Logs warning when no active stream for producer."""
    adapter.send_result_sync("ghost", {"r": 1})
    assert "No active stream found" in caplog.text


def test_send_result_sync_with_running_loop(adapter):
    """Dispatches via run_coroutine_threadsafe when loop is running."""
    queue = asyncio.Queue()
    producer = "prod_sync"
    adapter._active_streams[producer] = queue

    mock_loop = MagicMock()
    mock_loop.is_running.return_value = True
    mock_future = MagicMock()
    mock_future.result.return_value = None
    mock_loop.return_value = mock_future
    adapter._loop = mock_loop

    with patch("asyncio.run_coroutine_threadsafe", return_value=mock_future):
        adapter.send_result_sync(producer, {"v": 42})
    mock_future.result.assert_called_once_with(timeout=5)


def test_send_result_sync_loop_not_running(adapter, caplog):
    """Logs error when loop is not running."""
    queue = asyncio.Queue()
    producer = "prod_nloop"
    adapter._active_streams[producer] = queue

    mock_loop = MagicMock()
    mock_loop.is_running.return_value = False
    adapter._loop = mock_loop

    adapter.send_result_sync(producer, {"v": 1})
    assert "Event loop not running" in caplog.text


# ---------------------------------------------------------------------------
# stop and _handle_message
# ---------------------------------------------------------------------------

def test_stop_sets_running_false(adapter):
    """stop() sets _running to False."""
    adapter._running = True
    adapter.stop()
    assert adapter._running is False


def test_handle_message_is_noop(adapter):
    """_handle_message does nothing (pass)."""
    adapter._handle_message({"any": "message"})  # should not raise


# ---------------------------------------------------------------------------
# _load_jwt_config
# ---------------------------------------------------------------------------

def test_load_jwt_config_returns_dict(adapter):
    """_load_jwt_config returns the jwt section of config."""
    cfg = adapter._load_jwt_config()
    assert cfg["secret"] == _JWT_SECRET
    assert cfg["algorithm"] == _JWT_ALGORITHM


# ---------------------------------------------------------------------------
# _base64url_decode
# ---------------------------------------------------------------------------

def test_base64url_decode_basic(adapter):
    """Decodes standard base64url-encoded bytes correctly."""
    data = base64.urlsafe_b64encode(b"hello").rstrip(b"=").decode()
    assert adapter._base64url_decode(data) == b"hello"


# ---------------------------------------------------------------------------
# _verify_jwt – error paths
# ---------------------------------------------------------------------------

def test_verify_jwt_no_dot(adapter):
    with pytest.raises(ValueError, match="missing '\\.'"):
        adapter._verify_jwt("nodottoken")


def test_verify_jwt_wrong_part_count(adapter):
    with pytest.raises(ValueError, match="expected 3"):
        adapter._verify_jwt("a.b")


def test_verify_jwt_invalid_header_encoding(adapter):
    with pytest.raises(ValueError, match="Invalid JWT header"):
        adapter._verify_jwt("!!!.payload.sig")


def _make_hdr_b64(hdr):
    """Encode a JOSE header dict as base64url."""
    return base64.urlsafe_b64encode(
        json.dumps(hdr).encode()).rstrip(b"=").decode()


def test_verify_jwt_unsupported_header_key(adapter):
    hdr_b64 = _make_hdr_b64({"alg": "HS256", "x-custom": "bad"})
    with pytest.raises(ValueError, match="Unsupported JOSE header"):
        adapter._verify_jwt(f"{hdr_b64}.payload.sig")


def test_verify_jwt_invalid_typ(adapter):
    hdr_b64 = _make_hdr_b64({"alg": "HS256", "typ": "JWX"})
    with pytest.raises(ValueError, match="Invalid typ header"):
        adapter._verify_jwt(f"{hdr_b64}.payload.sig")


def test_verify_jwt_jwe_detected(adapter):
    # 5-part token (JWE format) is rejected even with a valid header
    hdr_b64 = _make_hdr_b64({"alg": "HS256"})
    with pytest.raises(ValueError, match="Encrypted JWTs"):
        adapter._verify_jwt(f"{hdr_b64}.a.b.c.d")


def test_verify_jwt_missing_alg(adapter):
    hdr_b64 = _make_hdr_b64({"typ": "JWT"})
    with pytest.raises(ValueError, match="Missing 'alg'"):
        adapter._verify_jwt(f"{hdr_b64}.payload.sig")


def test_verify_jwt_alg_none(adapter):
    hdr_b64 = _make_hdr_b64({"alg": "none"})
    with pytest.raises(ValueError, match="Unsecured JWTs"):
        adapter._verify_jwt(f"{hdr_b64}.payload.sig")


def test_verify_jwt_wrong_alg(adapter):
    hdr_b64 = _make_hdr_b64({"alg": "RS256"})
    with pytest.raises(ValueError, match="Disallowed alg"):
        adapter._verify_jwt(f"{hdr_b64}.payload.sig")


def test_verify_jwt_invalid_signature(adapter):
    hdr_b64 = _make_hdr_b64({"alg": "HS256"})
    pay = base64.urlsafe_b64encode(b"{}").rstrip(b"=").decode()
    with pytest.raises(ValueError, match="Invalid JWT signature"):
        adapter._verify_jwt(f"{hdr_b64}.{pay}.badsig")


def test_verify_jwt_nested_jwt(adapter):
    """Reject tokens with cty='JWT' (nested JWT)."""
    now = int(time.time())
    nested = pyjwt.encode(
        {"sub": "u", "exp": now + 3600, "iat": now},
        _JWT_SECRET, algorithm="HS256",
        headers={"cty": "JWT"}
    )
    with pytest.raises(ValueError, match="Nested JWTs"):
        adapter._verify_jwt(nested)


def test_verify_jwt_token_too_old(adapter):
    """Reject tokens whose iat is older than max_token_age_seconds."""
    old_iat = int(time.time()) - 7200  # 2 hours ago
    token = _make_jwt({"iat": old_iat, "exp": int(time.time()) + 3600})
    with pytest.raises(ValueError, match="Token too old"):
        adapter._verify_jwt(token)


def test_verify_jwt_valid(adapter):
    """Valid token returns decoded payload."""
    token = _make_jwt()
    payload = adapter._verify_jwt(token)
    assert payload["sub"] == "user1"


# ---------------------------------------------------------------------------
# _start_server
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_server_configures_and_calls_serve(adapter):
    """_start_server configures HyperConfig and calls serve."""
    with patch(
        "simulation_bridge.src.protocol_adapters.rest.rest_adapter.serve",
        new_callable=AsyncMock
    ) as mock_serve:
        await adapter._start_server()
        mock_serve.assert_called_once()
        assert adapter._loop is not None


@pytest.mark.asyncio
async def test_start_server_with_tls(adapter):
    """_start_server sets certfile/keyfile when both are present."""
    adapter.config['certfile'] = '/tmp/cert.pem'
    adapter.config['keyfile'] = '/tmp/key.pem'
    with patch(
        "simulation_bridge.src.protocol_adapters.rest.rest_adapter.serve",
        new_callable=AsyncMock
    ):
        await adapter._start_server()


def test_start_raises_and_logs_on_exception(adapter, caplog):
    """start() logs error and re-raises if asyncio.run fails."""
    with patch("asyncio.run", side_effect=RuntimeError("fail")):
        with pytest.raises(RuntimeError, match="fail"):
            adapter.start()
    assert "Error starting server" in caplog.text


# ---------------------------------------------------------------------------
# publish_result_message_rest – exception path
# ---------------------------------------------------------------------------

def test_publish_result_message_rest_connection_error(adapter, caplog):
    """publish_result_message_rest logs on ConnectionError."""
    with patch.object(adapter, 'send_result_sync',
                      side_effect=ConnectionError("conn fail")):
        adapter.publish_result_message_rest(
            None, message={'destinations': ['d1'], 'request_id': 'r1'})
    assert "Error sending result message" in caplog.text
