"""Unit-tests for InMemoryAdapter (pytest)."""

from unittest.mock import MagicMock

import pytest

from simulation_bridge.src.protocol_adapters.inmemory.inmemory_adapter import (
    InMemoryAdapter,
)


@pytest.fixture(name="cfg_mgr")
def fixture_config_manager():
    """Mock ConfigManager instance."""
    return MagicMock()


@pytest.fixture(name="inmemory_adapter")
def fixture_inmemory_adapter(cfg_mgr):
    """Fresh InMemoryAdapter instance for each test."""
    return InMemoryAdapter(cfg_mgr)


def test_start_stop_flags(inmemory_adapter):
    inmemory_adapter.start()
    assert inmemory_adapter.is_running is True
    inmemory_adapter.stop()
    assert inmemory_adapter.is_running is False


def test_send_stores_callback_and_emits_signal(inmemory_adapter, monkeypatch):
    send_mock = MagicMock()
    sig_factory_mock = MagicMock(return_value=MagicMock(send=send_mock))
    monkeypatch.setattr(
        "simulation_bridge.src.protocol_adapters.inmemory.inmemory_adapter.signal",
        sig_factory_mock,
    )

    message = {
        "simulation": {
            "request_id": "req-1",
            "client_id": "client-x",
            "simulator": "matlab",
        }
    }
    callback = MagicMock()

    inmemory_adapter.send(message, callback)

    assert inmemory_adapter._callbacks["req-1"] is callback  # pylint: disable=protected-access
    send_mock.assert_called_once()


def test_handle_result_keeps_callback_until_completed(inmemory_adapter):
    rid = "req-42"
    callback = MagicMock()
    inmemory_adapter._callbacks[rid] = callback  # pylint: disable=protected-access

    # in_progress status: callback called but kept registered
    inmemory_adapter._handle_result(  # pylint: disable=protected-access
        None,
        message={"request_id": rid, "status": "in_progress", "foo": 1},
    )
    callback.assert_called_with(
        {"request_id": rid, "status": "in_progress", "foo": 1}
    )
    assert rid in inmemory_adapter._callbacks  # pylint: disable=protected-access

    # completed status: callback called again and then removed
    inmemory_adapter._handle_result(  # pylint: disable=protected-access
        None,
        message={"request_id": rid, "status": "completed", "bar": 2},
    )
    assert callback.call_count == 2
    assert rid not in inmemory_adapter._callbacks  # pylint: disable=protected-access
