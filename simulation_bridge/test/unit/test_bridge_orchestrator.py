"""Test suite for the BridgeOrchestrator module."""
# pylint: disable=too-many-arguments,unused-argument,protected-access,redefined-outer-name

from unittest.mock import patch, MagicMock
import pytest
from simulation_bridge.src.core import bridge_orchestrator


@pytest.fixture
def mock_config(dummy_credentials):
    """Mock base configuration with complete RabbitMQ fields."""
    return {
        'simulation_bridge': {'bridge_id': 'bridge-123'},
        'rabbitmq': {
            'host': 'localhost',
            'port': 5672,
            'username': dummy_credentials['guest']['username'],
            'password': dummy_credentials['guest']['password'],
            'vhost': '/',
            'exchange': 'sim_exchange',
        }
    }


@pytest.fixture
def config_manager_mock(mock_config):
    """Fixture for mocking ConfigManager with valid config."""
    with patch(
        'simulation_bridge.src.core.bridge_orchestrator.ConfigManager'
    ) as mock_cm:
        instance = mock_cm.return_value
        instance.get_config.return_value = mock_config
        instance.get_rabbitmq_config.return_value = mock_config['rabbitmq']
        yield instance


@pytest.fixture
def orchestrator(config_manager_mock):
    """Returns BridgeOrchestrator instance with dependencies mocked."""
    with patch(
        'simulation_bridge.src.core.bridge_orchestrator.get_logger'
    ), patch(
        'simulation_bridge.src.core.bridge_orchestrator.ensure_certificates'
    ), patch(
        'simulation_bridge.src.core.bridge_orchestrator.load_protocol_config',
        return_value={'mqtt': {'class': 'mqtt_adapter.MQTTAdapter'}}
    ), patch(
        'simulation_bridge.src.core.bridge_orchestrator.importlib.import_module'
    ) as import_mod:
        mock_class = MagicMock()
        import_mod.return_value = MagicMock(MQTTAdapter=mock_class)
        return bridge_orchestrator.BridgeOrchestrator()


class TestSetupInterfaces:
    """Tests for BridgeOrchestrator.setup_interfaces method."""

    def test_setup_success(self, orchestrator):
        """Test successful setup with enabled protocols."""
        with patch(
            'simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure'
        ) as rabbit_mock, patch(
            'simulation_bridge.src.core.bridge_orchestrator.SignalManager'
        ) as signal_mock, patch(
            'simulation_bridge.src.core.bridge_orchestrator.BridgeCore'
        ) as core_mock:
            rabbit_instance = rabbit_mock.return_value
            rabbit_instance.setup.return_value = None

            signal_mock.get_enabled_protocols.return_value = ['mqtt']
            orchestrator.setup_interfaces()

            rabbit_instance.setup.assert_called_once()
            signal_mock.register_adapter_instance.assert_called_once()
            signal_mock.set_bridge_core.assert_called_once_with(
                core_mock.return_value)
            signal_mock.connect_all_signals.assert_called_once()

    def test_setup_raises_exception(self, orchestrator):
        """Test setup raises exception if infrastructure fails."""
        with patch(
            'simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure'
        ) as rabbit_mock:
            rabbit_instance = rabbit_mock.return_value
            rabbit_instance.setup.side_effect = ValueError("fail")
            with pytest.raises(ValueError):
                orchestrator.setup_interfaces()


class TestStartStop:
    """Tests for BridgeOrchestrator start/stop behavior."""

    def test_stop_clean_shutdown(self, orchestrator):
        """Ensure adapters and signals shut down cleanly."""
        adapter_mock = MagicMock()
        adapter_mock.thread = MagicMock()
        orchestrator.adapters = {'mqtt': adapter_mock}
        with patch(
            'simulation_bridge.src.core.bridge_orchestrator.SignalManager'
        ) as signal:
            orchestrator.stop()
            adapter_mock.stop.assert_called_once()
            adapter_mock.thread.join.assert_called_once()
            signal.disconnect_all_signals.assert_called_once()

    def test_start_keyboard_interrupt(self, orchestrator):
        adapter = MagicMock()
        adapter.is_running = True
        orchestrator.adapters = {'mqtt': adapter}
        with patch.object(orchestrator, 'setup_interfaces'), \
                patch('simulation_bridge.src.core.bridge_orchestrator.time.sleep',
                      side_effect=KeyboardInterrupt), \
                patch.object(orchestrator, 'stop') as stop_mock:
            try:
                orchestrator.start()
            except SystemExit:
                pass
            adapter.start.assert_called_once()
            stop_mock.assert_called_once()


class TestAdapterImport:  # pylint: disable=too-few-public-methods
    """Tests for internal _import_adapter_classes logic."""

    def test_import_adapter_classes(self, config_manager_mock):
        """Test dynamic loading of adapter classes from config."""
        with patch(
            'simulation_bridge.src.core.bridge_orchestrator.load_protocol_config',
            return_value={'mqtt': {'class': 'mqtt_adapter.MQTTAdapter'}}
        ), patch(
            'simulation_bridge.src.core.bridge_orchestrator.importlib.import_module'
        ) as import_mod, patch(
            'simulation_bridge.src.core.bridge_orchestrator.get_logger'
        ), patch(
            'simulation_bridge.src.core.bridge_orchestrator.ensure_certificates'
        ):
            mock_class = MagicMock()
            import_mod.return_value = MagicMock(MQTTAdapter=mock_class)
            orchestrator = bridge_orchestrator.BridgeOrchestrator()
            assert 'mqtt' in orchestrator.adapter_classes
            assert orchestrator.adapter_classes['mqtt'] == mock_class
