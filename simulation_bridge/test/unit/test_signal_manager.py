"""
Unit tests for the SignalManager module.
"""

from unittest import mock
import pytest
import blinker

from simulation_bridge.src.utils import signal_manager

# pylint: disable=too-many-arguments,unused-argument,protected-access,redefined-outer-name

pytestmark = pytest.mark.usefixtures("config_override")


@pytest.fixture(autouse=True)
def config_override(monkeypatch):
    """Override PROTOCOL_CONFIG for isolated tests"""
    test_config = {
        "proto_a": {"enabled": True, "signals": {"sig_x": "BridgeCore.handle_x"}},
        "proto_b": {"enabled": False, "signals": {"sig_y": "Adapter.do_y"}},
    }
    monkeypatch.setattr(
        signal_manager.SignalManager,
        'PROTOCOL_CONFIG',
        test_config)
    monkeypatch.setattr(signal_manager.SignalManager, '_adapter_instances', {})
    monkeypatch.setattr(
        signal_manager.SignalManager,
        '_bridge_core_instance',
        None)
    yield


@pytest.fixture
def bridge_core(monkeypatch):
    """Provide and set a mock BridgeCore instance"""
    core = mock.Mock()
    monkeypatch.setattr(
        signal_manager.SignalManager,
        '_bridge_core_instance',
        core)
    return core


@pytest.fixture
def adapter(monkeypatch):
    """Provide a mock adapter instance and registry"""
    adapter_inst = mock.Mock()
    adapter_inst.do_y = mock.Mock()
    monkeypatch.setattr(signal_manager.SignalManager, '_adapter_instances', {})
    return adapter_inst


class TestSignalQueries:
    """Tests for querying available and enabled protocols and signals"""

    def test_get_available_signals_returns_list(self):
        """Validate fetching signals for a valid protocol"""
        result = signal_manager.SignalManager.get_available_signals('proto_a')
        assert result == ['sig_x']

    def test_get_available_signals_empty_for_unknown(self):
        """Validate empty result for unknown protocol"""
        result = signal_manager.SignalManager.get_available_signals('unknown')
        assert not result

    def test_get_enabled_protocols_filters_disabled(self):
        """Ensure only enabled protocols are returned"""
        result = signal_manager.SignalManager.get_enabled_protocols()
        assert result == ['proto_a']

    @pytest.mark.parametrize(
        'proto, expected', [
            ('proto_a', True),
            ('proto_b', False),
            ('unknown', False),
        ]
    )
    def test_is_protocol_enabled(self, proto, expected):
        """Check enabled status across various protocols"""
        assert signal_manager.SignalManager.is_protocol_enabled(
            proto) is expected


class TestResolveCallback:
    """Tests for internal callback resolution logic"""

    def test_resolve_without_dot_returns_none(self):
        """Invalid func_path without dot yields None"""
        assert signal_manager.SignalManager._resolve_callback(
            'invalidpath', 'proto_a') is None

    def test_resolve_bridgecore_no_instance_logs_error(self, caplog):
        """Logging on missing BridgeCore instance"""
        caplog.set_level('ERROR')
        cb = signal_manager.SignalManager._resolve_callback(
            'BridgeCore.handle_x', 'proto_a')
        assert cb is None
        assert 'BridgeCore instance not set' in caplog.text

    def test_resolve_bridgecore_with_instance(self, bridge_core):
        """Successful resolution on BridgeCore instance"""
        bridge_core.handle_x = mock.Mock()
        cb = signal_manager.SignalManager._resolve_callback(
            'BridgeCore.handle_x', 'proto_a')
        assert cb == bridge_core.handle_x

    def test_resolve_adapter_method(self, adapter):
        """Resolution of registered adapter methods"""
        signal_manager.SignalManager.register_adapter_instance(
            'proto_b', adapter)
        cb = signal_manager.SignalManager._resolve_callback(
            'Adapter.do_y', 'proto_b')
        assert cb == adapter.do_y

    def test_resolve_no_adapter_logs_warning(self, caplog):
        """Logging on missing adapter registration"""
        caplog.set_level('WARNING')
        cb = signal_manager.SignalManager._resolve_callback(
            'Adapter.do_y', 'proto_b')
        assert cb is None
        assert 'No adapter instance registered' in caplog.text


class TestSignalConnections:
    """Tests for connecting and disconnecting signals"""

    @pytest.fixture(autouse=True)
    def setup_instances(self, bridge_core, adapter):
        """Register instances before testing signal connections"""
        signal_manager.SignalManager.register_adapter_instance(
            'proto_b', adapter)
        yield

    def test_connect_all_signals_success(self, bridge_core):
        """Connect and emit signals for enabled protocols"""
        sig = blinker.signal('sig_x')
        # Remove any existing receivers
        for receiver in list(sig.receivers.values()):
            sig.disconnect(receiver)

        signal_manager.SignalManager.connect_all_signals()
        sig.send()
        bridge_core.handle_x.assert_called_once()

    def test_disconnect_all_signals(self, bridge_core):
        """Disconnect previously connected signals"""
        sig = blinker.signal('sig_x')
        for receiver in list(sig.receivers.values()):
            sig.disconnect(receiver)
        signal_manager.SignalManager.connect_all_signals()

        signal_manager.SignalManager.disconnect_all_signals()
        bridge_core.handle_x.reset_mock()
        sig.send()
        bridge_core.handle_x.assert_not_called()

    def test_set_bridge_core_stores_instance(self, monkeypatch):
        """set_bridge_core stores the provided instance."""
        core = mock.Mock()
        signal_manager.SignalManager.set_bridge_core(core)
        assert signal_manager.SignalManager._bridge_core_instance is core

    def test_connect_all_signals_skips_disabled_protocol(self, caplog):
        """Disabled protocols are skipped with a debug log."""
        caplog.set_level('DEBUG', logger='SIMULATION-BRIDGE')
        signal_manager.SignalManager.connect_all_signals()
        assert 'Skipping signals for disabled protocol' in caplog.text

    def test_connect_all_signals_logs_on_exception(self, bridge_core, caplog):
        """connect_all_signals logs error when signal connection raises."""
        caplog.set_level('ERROR')
        with mock.patch.object(
            blinker.signal('sig_x'), 'connect',
            side_effect=RuntimeError("connect boom")
        ):
            signal_manager.SignalManager.connect_all_signals()
        assert "Failed to connect signal" in caplog.text

    def test_disconnect_all_signals_skips_disabled(self, caplog):
        """Disabled protocols are skipped during disconnect."""
        caplog.set_level('DEBUG', logger='SIMULATION-BRIDGE')
        signal_manager.SignalManager.disconnect_all_signals()
        assert 'Skipping signal disconnection for disabled protocol' in caplog.text

    def test_disconnect_all_signals_logs_on_exception(
            self, bridge_core, caplog):
        """disconnect_all_signals logs error when disconnect raises."""
        caplog.set_level('ERROR')
        signal_manager.SignalManager.connect_all_signals()
        with mock.patch.object(
            blinker.signal('sig_x'), 'disconnect',
            side_effect=RuntimeError("disc boom")
        ):
            signal_manager.SignalManager.disconnect_all_signals()
        assert "Failed to disconnect signal" in caplog.text


class TestConnectInmemorySignals:
    """Tests for connect_inmemory_signals method."""

    @pytest.fixture(autouse=True)
    def setup_inmemory_config(self, monkeypatch):
        """Provide a config with an inmemory protocol."""
        test_config = {
            "inmemory": {
                "enabled": True,
                "signals": {"sig_inmem": "BridgeCore.handle_inmem"}
            },
        }
        monkeypatch.setattr(
            signal_manager.SignalManager, 'PROTOCOL_CONFIG', test_config)
        monkeypatch.setattr(
            signal_manager.SignalManager, '_adapter_instances', {})
        monkeypatch.setattr(
            signal_manager.SignalManager, '_bridge_core_instance', None)
        yield

    def test_connect_inmemory_signals_connects(self, monkeypatch):
        """connect_inmemory_signals connects signals for inmemory protocol."""
        core = mock.Mock()
        core.handle_inmem = mock.Mock()
        monkeypatch.setattr(
            signal_manager.SignalManager, '_bridge_core_instance', core)
        sig = blinker.signal('sig_inmem')
        for r in list(sig.receivers.values()):
            sig.disconnect(r)
        signal_manager.SignalManager.connect_inmemory_signals()
        sig.send()
        core.handle_inmem.assert_called_once()

    def test_connect_inmemory_signals_disabled(self, monkeypatch, caplog):
        """connect_inmemory_signals skips when inmemory is disabled."""
        caplog.set_level('DEBUG', logger='SIMULATION-BRIDGE')
        monkeypatch.setattr(
            signal_manager.SignalManager, 'PROTOCOL_CONFIG',
            {"inmemory": {"enabled": False, "signals": {}}})
        signal_manager.SignalManager.connect_inmemory_signals()
        assert "Skipping" in caplog.text

    def test_connect_inmemory_signals_missing_protocol(
            self, monkeypatch, caplog):
        """connect_inmemory_signals skips gracefully if inmemory missing."""
        caplog.set_level('DEBUG', logger='SIMULATION-BRIDGE')
        monkeypatch.setattr(
            signal_manager.SignalManager, 'PROTOCOL_CONFIG', {})
        signal_manager.SignalManager.connect_inmemory_signals()
        assert "Skipping" in caplog.text


class TestResolveCallbackStrictProtocol:
    """Tests for strict_protocol filtering in _resolve_callback."""

    def test_strict_protocol_mismatch_returns_none(self, caplog):
        """When strict_protocol differs from protocol, return None."""
        caplog.set_level('DEBUG')
        cb = signal_manager.SignalManager._resolve_callback(
            'Adapter.method', 'proto_a', strict_protocol='proto_b')
        assert cb is None
