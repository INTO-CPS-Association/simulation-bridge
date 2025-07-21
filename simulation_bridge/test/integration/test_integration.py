
"""Integration tests for simulation bridge components."""
import logging
from unittest.mock import patch, MagicMock
import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from simulation_bridge.src.core.bridge_orchestrator import BridgeOrchestrator
from simulation_bridge.src.core.bridge_core import BridgeCore
from simulation_bridge.src.core.bridge_infrastructure import RabbitMQInfrastructure
from simulation_bridge.src.utils.signal_manager import SignalManager
from simulation_bridge.src.utils.certs import CertificateGenerator, ensure_certificates

# pylint: disable=too-many-arguments, unused-argument, protected-access, import-outside-toplevel
# pylint: disable=redefined-outer-name, attribute-defined-outside-init, reimported


@pytest.fixture
def mock_config_manager(dummy_credentials):
    """Mock configuration manager fixture."""
    mock = MagicMock()
    mock.get_config.return_value = {
        'simulation_bridge': {'bridge_id': 'test-bridge'},
        'rabbitmq': {
            'host': 'localhost',
            'port': 5672,
            'username': dummy_credentials['guest']['username'],
            'password': dummy_credentials['guest']['password'],
            'vhost': '/',
            'infrastructure': {
                'exchanges': [],
                'queues': [],
                'bindings': []
            }
        }
    }
    mock.get_rabbitmq_config.return_value = mock.get_config.return_value['rabbitmq']
    return mock


def test_bridge_infrastructure_setup(mock_config_manager):
    """Test bridge infrastructure setup."""
    with patch("pika.BlockingConnection"):
        infra = RabbitMQInfrastructure(mock_config_manager)
        with patch.object(infra, "_setup_exchanges") as mock_ex, \
                patch.object(infra, "_setup_queues") as mock_qu, \
                patch.object(infra, "_setup_bindings") as mock_bi, \
                patch.object(infra.connection, "close"):
            infra.setup()
            mock_ex.assert_called_once()
            mock_qu.assert_called_once()
            mock_bi.assert_called_once()


def test_bridge_infrastructure_setup_exception(mock_config_manager):
    """Test bridge infrastructure setup with exception."""
    with patch("pika.BlockingConnection"):
        infra = RabbitMQInfrastructure(mock_config_manager)
        with patch.object(infra, "_setup_exchanges", side_effect=Exception("fail")), \
                patch.object(infra.connection, "close"):
            with pytest.raises(Exception):
                infra.setup()


def test_bridge_infrastructure_reconnect(mock_config_manager):
    """Test bridge infrastructure reconnection."""
    with patch("pika.BlockingConnection"):
        infra = RabbitMQInfrastructure(mock_config_manager)
        infra.connection.is_closed = True
        with patch("pika.BlockingConnection"):
            conn = infra.reconnect()
            assert conn is not None


def test_bridge_core_init(mock_config_manager):
    """Test bridge core initialization."""
    adapters = {}
    with patch("pika.BlockingConnection"):
        core = BridgeCore(mock_config_manager, adapters)
        assert core.adapters == adapters
        assert core.channel is not None


def test_bridge_core_handle_input_message_valid(
        monkeypatch, mock_config_manager):
    """Test bridge core handling valid input message."""
    adapters = {}
    with patch("pika.BlockingConnection"):
        core = BridgeCore(mock_config_manager, adapters)
        # Patch _publish_message to avoid side effects
        monkeypatch.setattr(core, "_publish_message", lambda *a, **kw: None)
        valid_message = {
            'simulation': {
                'request_id': '1',
                'client_id': 'c',
                'simulator': 'sim',
                'type': 't',
                'file': 'f',
                'inputs': {},
                'outputs': {}
            }
        }
        core.handle_input_message(
            None,
            message=valid_message,
            producer='p',
            consumer='c',
            protocol='rabbitmq')


def test_bridge_core_handle_input_message_invalid(
        monkeypatch, mock_config_manager):
    """Test bridge core handling invalid input message."""
    adapters = {}
    with patch("pika.BlockingConnection"):
        core = BridgeCore(mock_config_manager, adapters)
        monkeypatch.setattr(core, "_publish_message", lambda *a, **kw: None)
        # message missing 'simulation'
        core.handle_input_message(
            None,
            message={},
            producer='p',
            consumer='c',
            protocol='rabbitmq')


def test_bridge_core_handle_result_rabbitmq_message(
        monkeypatch, mock_config_manager):
    """Test bridge core handling result RabbitMQ message."""
    adapters = {}
    with patch("pika.BlockingConnection"):
        core = BridgeCore(mock_config_manager, adapters)
        monkeypatch.setattr(core, "_publish_message", lambda *a, **kw: None)
        core.handle_result_rabbitmq_message(None, message={'source': 'src'})


def test_bridge_core_handle_result_unknown_message(mock_config_manager):
    """Test bridge core handling unknown result message."""
    adapters = {}
    with patch("pika.BlockingConnection"):
        core = BridgeCore(mock_config_manager, adapters)
        # Pass the 'error' key as well
        core.handle_result_unknown_message(
            None, message={'foo': 'bar', 'error': 'some error'})


def test_bridge_orchestrator_setup_interfaces_enabled(mock_config_manager):
    """Test bridge orchestrator setup interfaces when enabled."""
    mock_infra_path = "simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure"
    mock_signal_path = "simulation_bridge.src.core.bridge_orchestrator.SignalManager"
    mock_core_path = "simulation_bridge.src.core.bridge_orchestrator.BridgeCore"
    mock_cert_path = "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates"
    mock_proto_path = "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config"

    with patch(mock_infra_path) as mock_infra, \
            patch(mock_signal_path) as mock_signal_manager, \
            patch(mock_core_path) as mock_bridge_core, \
            patch(mock_cert_path), \
            patch(mock_proto_path) as mock_proto_conf:

        mock_proto_conf.return_value = {
            "mqtt": {"class": "mqtt_adapter.MQTTAdapter", "enabled": True, "signals": {}}
        }
        mock_signal_manager.get_enabled_protocols.return_value = ["mqtt"]
        mock_signal_manager.register_adapter_instance.return_value = None
        mock_signal_manager.set_bridge_core.return_value = None
        mock_signal_manager.connect_all_signals.return_value = None

        with patch("importlib.import_module") as mock_import:
            mock_adapter_class = MagicMock()
            mock_import.return_value = MagicMock(MQTTAdapter=mock_adapter_class)
            orchestrator = BridgeOrchestrator()
            orchestrator.config_manager = mock_config_manager
            orchestrator.protocol_config = mock_proto_conf.return_value
            orchestrator.adapter_classes = {"mqtt": mock_adapter_class}
            orchestrator.setup_interfaces()
            mock_infra.assert_called_once()
            mock_bridge_core.assert_called_once()


def test_bridge_orchestrator_setup_interfaces_no_enabled(mock_config_manager):
    """Test bridge orchestrator setup interfaces when none enabled."""
    mock_infra_path = "simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure"
    mock_signal_path = "simulation_bridge.src.core.bridge_orchestrator.SignalManager"
    mock_core_path = "simulation_bridge.src.core.bridge_orchestrator.BridgeCore"
    mock_cert_path = "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates"
    mock_proto_path = "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config"

    with patch(mock_infra_path) as mock_infra, \
            patch(mock_signal_path) as mock_signal_manager, \
            patch(mock_core_path) as mock_bridge_core, \
            patch(mock_cert_path), \
            patch(mock_proto_path) as mock_proto_conf:

        mock_proto_conf.return_value = {
            "mqtt": {"class": "mqtt_adapter.MQTTAdapter", "enabled": False, "signals": {}}
        }
        mock_signal_manager.get_enabled_protocols.return_value = []
        with patch("importlib.import_module"):
            orchestrator = BridgeOrchestrator()
            orchestrator.config_manager = mock_config_manager
            orchestrator.protocol_config = mock_proto_conf.return_value
            orchestrator.adapter_classes = {}
            orchestrator.setup_interfaces()
            mock_infra.assert_called_once()
            mock_bridge_core.assert_called_once_with(mock_config_manager, {})


def test_bridge_orchestrator_setup_interfaces_exception(mock_config_manager):
    """Test bridge orchestrator setup interfaces with exception."""
    mock_infra_path = "simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure"
    mock_cert_path = "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates"
    mock_proto_path = "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config"

    with patch(mock_infra_path, side_effect=Exception("fail")), \
            patch(mock_cert_path), \
            patch(mock_proto_path) as mock_proto_conf:
        mock_proto_conf.return_value = {}
        orchestrator = BridgeOrchestrator()
        orchestrator.config_manager = mock_config_manager
        orchestrator.protocol_config = {}
        orchestrator.adapter_classes = {}
        with pytest.raises(Exception):
            orchestrator.setup_interfaces()


def test_bridge_orchestrator_signal_manager_integration(mock_config_manager):
    """Test bridge orchestrator signal manager integration."""
    mock_infra_path = "simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure"
    mock_signal_path = "simulation_bridge.src.core.bridge_orchestrator.SignalManager"
    mock_core_path = "simulation_bridge.src.core.bridge_orchestrator.BridgeCore"
    mock_cert_path = "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates"
    mock_proto_path = "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config"

    # Patch all external dependencies and protocol adapters
    with patch(mock_infra_path), \
            patch(mock_signal_path) as mock_signal_manager, \
            patch(mock_core_path), \
            patch(mock_cert_path), \
            patch(mock_proto_path) as mock_proto_conf:

        # Simulate protocol configuration with signals
        mock_proto_conf.return_value = {
            "mqtt": {
                "class": "mqtt_adapter.MQTTAdapter",
                "enabled": True,
                "signals": {
                    "on_message": "MQTTAdapter.on_message"
                }
            }
        }
        mock_signal_manager.get_enabled_protocols.return_value = ["mqtt"]
        mock_signal_manager.register_adapter_instance.return_value = None
        mock_signal_manager.set_bridge_core.return_value = None
        mock_signal_manager.connect_all_signals.return_value = None

        # Simulate importlib for the adapter
        with patch("importlib.import_module") as mock_import:
            mock_adapter_class = MagicMock()
            mock_import.return_value = MagicMock(MQTTAdapter=mock_adapter_class)
            orchestrator = BridgeOrchestrator()
            orchestrator.config_manager = mock_config_manager
            orchestrator.protocol_config = mock_proto_conf.return_value
            orchestrator.adapter_classes = {"mqtt": mock_adapter_class}
            orchestrator.setup_interfaces()

            # Verify that SignalManager was used to register and connect signals
            mock_signal_manager.register_adapter_instance.assert_called_with(
                "mqtt", mock_adapter_class(mock_config_manager))
            mock_signal_manager.set_bridge_core.assert_called()
            mock_signal_manager.connect_all_signals.assert_called()


def test_signal_manager_connect_and_disconnect(monkeypatch):
    """Test signal manager connect and disconnect."""
    # Use real SignalManager, patch logger and config
    class DummyAdapter:
        """Dummy adapter for testing."""

        def on_message(self):
            """Dummy message handler."""

    dummy_adapter = DummyAdapter()
    protocol = "dummy"
    func_path = "DummyAdapter.on_message"

    monkeypatch.setattr(SignalManager, "PROTOCOL_CONFIG", {
        "dummy": {
            "enabled": True,
            "signals": {"on_message": func_path}
        }
    })
    SignalManager.register_adapter_instance(protocol, dummy_adapter)

    # Patch _resolve_callback to return the correct method
    monkeypatch.setattr(
        SignalManager,
        "_resolve_callback",
        lambda func_path, protocol: dummy_adapter.on_message)

    # Connect and disconnect should not raise exceptions
    SignalManager.connect_all_signals()
    SignalManager.disconnect_all_signals()


def test_bridge_orchestrator_init_calls_ensure_certificates(monkeypatch):
    """Test bridge orchestrator init calls ensure certificates."""
    called = {}

    def fake_ensure_certificates(**kwargs):  # pylint: disable=unused-argument
        called['called'] = True

    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates",
        fake_ensure_certificates)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ConfigManager",
        MagicMock())
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config",
        lambda *a, **k: {})
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes",
        lambda self: {})
    BridgeOrchestrator()
    assert called.get('called')


def test_bridge_orchestrator_init_ensure_certificates_exception(monkeypatch):
    """Test bridge orchestrator init with ensure certificates exception."""
    def fake_ensure_certificates(**kwargs):  # pylint: disable=unused-argument
        raise RuntimeError("Cert error")

    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates",
        fake_ensure_certificates)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ConfigManager",
        MagicMock())
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config",
        lambda *a, **k: {})
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes",
        lambda self: {})
    with pytest.raises(RuntimeError, match="Cert error"):
        BridgeOrchestrator()


def test_bridge_orchestrator_init_certificates_custom_days(monkeypatch):
    """Test bridge orchestrator init with custom certificate validity days."""
    params = {}

    def fake_ensure_certificates(**kwargs):
        params.update(kwargs)

    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates",
        fake_ensure_certificates)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ConfigManager",
        MagicMock())
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config",
        lambda *a, **k: {})
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes",
        lambda self: {})
    BridgeOrchestrator()
    assert params.get("validity_days") == 365


def test_bridge_orchestrator_start_and_stop(monkeypatch, mock_config_manager):
    """Test that start and stop call SignalManager.disconnect_all_signals and stop on adapters."""
    monkeypatch.setattr(
        "simulation_bridge.src.utils.certs.ensure_certificates",
        lambda **kwargs: None)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ConfigManager",
        lambda *a, **k: mock_config_manager)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config",
        lambda *a, **k: {})
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes",
        lambda self: {})
    orchestrator = BridgeOrchestrator()
    orchestrator.adapters = {"mqtt": MagicMock(), "rest": MagicMock()}
    signal_path = "simulation_bridge.src.utils.signal_manager.SignalManager.disconnect_all_signals"
    with patch(signal_path) as disconnect_mock:
        orchestrator.stop()
        disconnect_mock.assert_called_once()
        for adapter in orchestrator.adapters.values():
            adapter.stop.assert_called_once()


def test_bridge_orchestrator_logs_bridge_id(monkeypatch, caplog):
    """Test that bridge ID is logged during initialization."""
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates",
        lambda **kwargs: None)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ConfigManager",
        lambda *a, **k: MagicMock(
            get_config=lambda: {
                'simulation_bridge': {'bridge_id': 'test-bridge'},
                'rabbitmq': {}}))
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config",
        lambda *a, **k: {})
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes",
        lambda self: {})
    with caplog.at_level(logging.INFO):
        BridgeOrchestrator()
    assert "Simulation bridge ID: test-bridge" in caplog.text


def test_bridge_orchestrator_logs_enabled_protocols(monkeypatch, caplog):
    """Test that enabled protocols are logged."""
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates",
        lambda **kwargs: None)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ConfigManager",
        lambda *a, **k: MagicMock(
            get_config=lambda: {
                'simulation_bridge': {'bridge_id': 'test-bridge'},
                'rabbitmq': {}}))
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config",
        lambda *a, **k: {
            "mqtt": {
                "class": "mqtt_adapter.MQTTAdapter",
                "enabled": True}})
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes",
        lambda self: {"mqtt": MagicMock(return_value=MagicMock())})

    mock_infra_path = "simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure"
    mock_signal_path = "simulation_bridge.src.core.bridge_orchestrator.SignalManager"
    mock_core_path = "simulation_bridge.src.core.bridge_orchestrator.BridgeCore"

    with patch(mock_infra_path), \
            patch(mock_signal_path) as mock_signal_manager, \
            patch(mock_core_path):
        mock_signal_manager.get_enabled_protocols.return_value = ["mqtt"]
        mock_signal_manager.register_adapter_instance.return_value = None
        mock_signal_manager.set_bridge_core.return_value = None
        mock_signal_manager.connect_all_signals.return_value = None
        orchestrator = BridgeOrchestrator()
        with caplog.at_level(logging.INFO):
            orchestrator.setup_interfaces()
        assert "Enabled protocols: MQTT" in caplog.text


def test_bridge_orchestrator_logs_no_enabled_protocols(monkeypatch, caplog):
    """Test that warning is logged when no protocols are enabled."""
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates",
        lambda **kwargs: None)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ConfigManager",
        lambda *a, **k: MagicMock(
            get_config=lambda: {
                'simulation_bridge': {'bridge_id': 'test-bridge'},
                'rabbitmq': {}}))
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config",
        lambda *a, **k: {
            "mqtt": {
                "class": "mqtt_adapter.MQTTAdapter",
                "enabled": False}})
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes",
        lambda self: {"mqtt": MagicMock(return_value=MagicMock())})

    mock_infra_path = "simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure"
    mock_signal_path = "simulation_bridge.src.core.bridge_orchestrator.SignalManager"
    mock_core_path = "simulation_bridge.src.core.bridge_orchestrator.BridgeCore"

    with patch(mock_infra_path), \
            patch(mock_signal_path) as mock_signal_manager, \
            patch(mock_core_path):
        mock_signal_manager.get_enabled_protocols.return_value = []
        orchestrator = BridgeOrchestrator()
        with caplog.at_level(logging.WARNING):
            orchestrator.setup_interfaces()
        assert "No protocol adapters are enabled" in caplog.text


def test_bridge_orchestrator_logs_error_on_exception(monkeypatch, caplog):
    """Test that error is logged when setup_interfaces raises exception."""
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates",
        lambda **kwargs: None)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ConfigManager",
        lambda *a, **k: MagicMock(
            get_config=lambda: {
                'simulation_bridge': {'bridge_id': 'test-bridge'},
                'rabbitmq': {}}))
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config",
        lambda *a, **k: {})
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes",
        lambda self: {})

    mock_infra_path = "simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure"
    with patch(mock_infra_path, side_effect=Exception("fail")):
        orchestrator = BridgeOrchestrator()
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception):
                orchestrator.setup_interfaces()
        assert "Error setting up interfaces: fail" in caplog.text


def test_bridge_orchestrator_certificates_validation_valid(
        monkeypatch, tmp_path):
    """Test that bridge orchestrator works with valid existing certificates."""
    # Create valid certificates
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generator = CertificateGenerator()
    success, _ = generator.generate_certificate_pair(
        str(cert_path), str(key_path))
    assert success

    # Mock ensure_certificates to use our test paths
    def mock_ensure_certificates(**kwargs):
        kwargs['cert_path'] = str(cert_path)
        kwargs['key_path'] = str(key_path)
        # Call real function with test paths
        ensure_certificates(**kwargs)

    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates",
        mock_ensure_certificates)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ConfigManager",
        lambda *a, **k: MagicMock(
            get_config=lambda: {
                'simulation_bridge': {'bridge_id': 'test-bridge'},
                'rabbitmq': {}}))
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config",
        lambda *a, **k: {})
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes",
        lambda self: {})

    # Should not raise exception
    BridgeOrchestrator()


def test_bridge_orchestrator_certificates_validation_expired(
        monkeypatch, tmp_path, caplog):
    """Test that bridge orchestrator regenerates expired certificates."""
    # Create expired certificates manually
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Create expired certificate (expired yesterday)
    now = datetime.datetime.now(datetime.timezone.utc)
    expired_date = now - datetime.timedelta(days=1)

    subject_name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Company"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject_name)
        .issuer_name(subject_name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(expired_date - datetime.timedelta(days=365))
        .not_valid_after(expired_date)  # Expired
        .sign(private_key, hashes.SHA256())
    )

    # Write the expired certificate and key
    with open(cert_path, "wb") as file:
        file.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(key_path, "wb") as file:
        file.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    def mock_ensure_certificates(**kwargs):
        kwargs['cert_path'] = str(cert_path)
        kwargs['key_path'] = str(key_path)
        ensure_certificates(**kwargs)

    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates",
        mock_ensure_certificates)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ConfigManager",
        lambda *a, **k: MagicMock(
            get_config=lambda: {
                'simulation_bridge': {'bridge_id': 'test-bridge'},
                'rabbitmq': {}}))
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config",
        lambda *a, **k: {})
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes",
        lambda self: {})

    with caplog.at_level(logging.ERROR):
        BridgeOrchestrator()
    assert "Existing certificates are invalid" in caplog.text


def test_bridge_orchestrator_certificates_missing_files(
        monkeypatch, tmp_path, caplog):
    """Test that bridge orchestrator generates certificates when files are missing."""
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"

    def mock_ensure_certificates(**kwargs):
        kwargs['cert_path'] = str(cert_path)
        kwargs['key_path'] = str(key_path)
        from simulation_bridge.src.utils.certs import ensure_certificates as real_ensure
        real_ensure(**kwargs)

    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates",
        mock_ensure_certificates)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ConfigManager",
        lambda *a,
        **k: MagicMock(
            get_config=lambda: {
                'simulation_bridge': {
                    'bridge_id': 'test-bridge'},
                'rabbitmq': {}}))
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config",
        lambda *a, **k: {})
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes",
        lambda self: {})

    with caplog.at_level(logging.INFO):
        BridgeOrchestrator()
    assert "SSL certificates generated successfully" in caplog.text
    assert cert_path.exists()
    assert key_path.exists()


def test_bridge_orchestrator_certificates_corrupted_files(
        monkeypatch, tmp_path, caplog):
    """Test that bridge orchestrator handles corrupted certificate files."""
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"

    # Create corrupted files
    cert_path.write_text("corrupted cert data")
    key_path.write_text("corrupted key data")

    def mock_ensure_certificates(**kwargs):
        kwargs['cert_path'] = str(cert_path)
        kwargs['key_path'] = str(key_path)
        from simulation_bridge.src.utils.certs import ensure_certificates as real_ensure
        real_ensure(**kwargs)

    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates",
        mock_ensure_certificates)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ConfigManager",
        lambda *a,
        **k: MagicMock(
            get_config=lambda: {
                'simulation_bridge': {
                    'bridge_id': 'test-bridge'},
                'rabbitmq': {}}))
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config",
        lambda *a, **k: {})
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes",
        lambda self: {})

    with caplog.at_level(logging.ERROR):
        BridgeOrchestrator()
    assert "Existing certificates are invalid" in caplog.text


def test_bridge_orchestrator_certificates_permission_error(
        monkeypatch, tmp_path):
    """Test that bridge orchestrator handles permission errors during certificate generation."""
    def mock_ensure_certificates(**kwargs):
        # Simulate permission error without actually creating read-only files
        raise RuntimeError(
            "Certificate generation failed: [Errno 13] Permission denied: '/test/path/cert.pem'")

    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ensure_certificates",
        mock_ensure_certificates)
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.ConfigManager",
        lambda *a,
        **k: MagicMock(
            get_config=lambda: {
                'simulation_bridge': {
                    'bridge_id': 'test-bridge'},
                'rabbitmq': {}}))
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.load_protocol_config",
        lambda *a, **k: {})
    monkeypatch.setattr(
        "simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes",
        lambda self: {})

    with pytest.raises(RuntimeError, match="Certificate generation failed"):
        BridgeOrchestrator()


def test_logger_setup_and_get_logger(tmp_path, caplog):
    """Test setup_logger creates file and console handlers, and
    get_logger returns the same instance."""
    from simulation_bridge.src.utils import logger as logger_mod

    log_file = tmp_path / "test.log"
    # Setup logger
    log = logger_mod.setup_logger(
        name="TEST-LOGGER",
        level=logger_mod.logging.DEBUG,
        log_file=str(log_file),
        enable_console=True
    )
    # Log a message
    log.info("Logger integration test message")
    # Check file was created and contains the message
    log.handlers[0].flush()
    with open(log_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Logger integration test message" in content

    # get_logger returns the same logger
    log2 = logger_mod.get_logger("TEST-LOGGER")
    assert log is log2


def test_logger_console_colored_output(monkeypatch, capsys):
    """Test that console handler uses colorlog.ColoredFormatter."""
    from simulation_bridge.src.utils import logger as logger_mod

    # Patch colorlog.ColoredFormatter to track usage
    called = {}
    orig_colored_formatter = logger_mod.colorlog.ColoredFormatter

    def fake_colored_formatter(*args, **kwargs):
        called['used'] = True
        return orig_colored_formatter(*args, **kwargs)
    monkeypatch.setattr(
        logger_mod.colorlog,
        "ColoredFormatter",
        fake_colored_formatter)

    log = logger_mod.setup_logger(name="COLOR-LOGGER", enable_console=True)
    log.info("Color test message")
    assert called.get('used')


def test_logger_no_duplicate_handlers(tmp_path):
    """Test that setup_logger does not add duplicate handlers if called twice."""
    from simulation_bridge.src.utils import logger as logger_mod

    log_file = tmp_path / "dup.log"
    log = logger_mod.setup_logger(name="DUP-LOGGER", log_file=str(log_file))
    n_handlers = len(log.handlers)
    # Call again, should not add more handlers
    log2 = logger_mod.setup_logger(name="DUP-LOGGER", log_file=str(log_file))
    assert len(log2.handlers) == n_handlers
