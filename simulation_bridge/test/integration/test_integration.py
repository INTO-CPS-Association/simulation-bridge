import pytest
from unittest.mock import patch, MagicMock
import logging

from simulation_bridge.src.core.bridge_orchestrator import BridgeOrchestrator
from simulation_bridge.src.core.bridge_core import BridgeCore
from simulation_bridge.src.core.bridge_infrastructure import RabbitMQInfrastructure
from simulation_bridge.src.utils.signal_manager import SignalManager

@pytest.fixture
def mock_config_manager():
    mock = MagicMock()
    mock.get_config.return_value = {
        'simulation_bridge': {'bridge_id': 'test-bridge'},
        'rabbitmq': {
            'host': 'localhost',
            'port': 5672,
            'username': 'guest',
            'password': 'guest',
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
    with patch("pika.BlockingConnection"):
        infra = RabbitMQInfrastructure(mock_config_manager)
        with patch.object(infra, "_setup_exchanges") as ex, \
             patch.object(infra, "_setup_queues") as qu, \
             patch.object(infra, "_setup_bindings") as bi, \
             patch.object(infra.connection, "close"):
            infra.setup()
            ex.assert_called_once()
            qu.assert_called_once()
            bi.assert_called_once()

def test_bridge_infrastructure_setup_exception(mock_config_manager):
    with patch("pika.BlockingConnection"):
        infra = RabbitMQInfrastructure(mock_config_manager)
        with patch.object(infra, "_setup_exchanges", side_effect=Exception("fail")), \
             patch.object(infra.connection, "close"):
            with pytest.raises(Exception):
                infra.setup()

def test_bridge_infrastructure_reconnect(mock_config_manager):
    with patch("pika.BlockingConnection"):
        infra = RabbitMQInfrastructure(mock_config_manager)
        infra.connection.is_closed = True
        with patch("pika.BlockingConnection"):
            conn = infra.reconnect()
            assert conn is not None

def test_bridge_core_init(mock_config_manager):
    adapters = {}
    with patch("pika.BlockingConnection"):
        core = BridgeCore(mock_config_manager, adapters)
        assert core.adapters == adapters
        assert core.channel is not None

def test_bridge_core_handle_input_message_valid(monkeypatch, mock_config_manager):
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
        core.handle_input_message(None, message=valid_message, producer='p', consumer='c', protocol='rabbitmq')

def test_bridge_core_handle_input_message_invalid(monkeypatch, mock_config_manager):
    adapters = {}
    with patch("pika.BlockingConnection"):
        core = BridgeCore(mock_config_manager, adapters)
        monkeypatch.setattr(core, "_publish_message", lambda *a, **kw: None)
        # message missing 'simulation'
        core.handle_input_message(None, message={}, producer='p', consumer='c', protocol='rabbitmq')

def test_bridge_core_handle_result_rabbitmq_message(monkeypatch, mock_config_manager):
    adapters = {}
    with patch("pika.BlockingConnection"):
        core = BridgeCore(mock_config_manager, adapters)
        monkeypatch.setattr(core, "_publish_message", lambda *a, **kw: None)
        core.handle_result_rabbitmq_message(None, message={'source': 'src'})

def test_bridge_core_handle_result_unknown_message(mock_config_manager):
    adapters = {}
    with patch("pika.BlockingConnection"):
        core = BridgeCore(mock_config_manager, adapters)
        # Passa anche la chiave 'error'
        core.handle_result_unknown_message(None, message={'foo': 'bar', 'error': 'some error'})

def test_bridge_orchestrator_setup_interfaces_enabled(monkeypatch, mock_config_manager):
    with patch("simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure") as MockInfra, \
         patch("simulation_bridge.src.core.bridge_orchestrator.SignalManager") as MockSignalManager, \
         patch("simulation_bridge.src.core.bridge_orchestrator.BridgeCore") as MockBridgeCore, \
         patch("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates"), \
         patch("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config") as mock_proto_conf:

        mock_proto_conf.return_value = {
            "mqtt": {"class": "mqtt_adapter.MQTTAdapter", "enabled": True, "signals": {}}
        }
        MockSignalManager.get_enabled_protocols.return_value = ["mqtt"]
        MockSignalManager.register_adapter_instance.return_value = None
        MockSignalManager.set_bridge_core.return_value = None
        MockSignalManager.connect_all_signals.return_value = None

        with patch("importlib.import_module") as mock_import:
            mock_adapter_class = MagicMock()
            mock_import.return_value = MagicMock(MQTTAdapter=mock_adapter_class)
            orchestrator = BridgeOrchestrator()
            orchestrator.config_manager = mock_config_manager
            orchestrator.protocol_config = mock_proto_conf.return_value
            orchestrator.adapter_classes = {"mqtt": mock_adapter_class}
            orchestrator.setup_interfaces()
            MockInfra.assert_called_once()
            MockBridgeCore.assert_called_once()

def test_bridge_orchestrator_setup_interfaces_no_enabled(monkeypatch, mock_config_manager):
    with patch("simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure") as MockInfra, \
         patch("simulation_bridge.src.core.bridge_orchestrator.SignalManager") as MockSignalManager, \
         patch("simulation_bridge.src.core.bridge_orchestrator.BridgeCore") as MockBridgeCore, \
         patch("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates"), \
         patch("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config") as mock_proto_conf:

        mock_proto_conf.return_value = {
            "mqtt": {"class": "mqtt_adapter.MQTTAdapter", "enabled": False, "signals": {}}
        }
        MockSignalManager.get_enabled_protocols.return_value = []
        with patch("importlib.import_module"):
            orchestrator = BridgeOrchestrator()
            orchestrator.config_manager = mock_config_manager
            orchestrator.protocol_config = mock_proto_conf.return_value
            orchestrator.adapter_classes = {}
            orchestrator.setup_interfaces()
            MockInfra.assert_called_once()
            MockBridgeCore.assert_called_once_with(mock_config_manager, {})

def test_bridge_orchestrator_setup_interfaces_exception(monkeypatch, mock_config_manager):
    with patch("simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure", side_effect=Exception("fail")), \
         patch("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates"), \
         patch("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config") as mock_proto_conf:
        mock_proto_conf.return_value = {}
        orchestrator = BridgeOrchestrator()
        orchestrator.config_manager = mock_config_manager
        orchestrator.protocol_config = {}
        orchestrator.adapter_classes = {}
        with pytest.raises(Exception):
            orchestrator.setup_interfaces()

def test_bridge_orchestrator_signal_manager_integration(monkeypatch, mock_config_manager):
    # Patch all external dependencies and protocol adapters
    with patch("simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure") as MockInfra, \
         patch("simulation_bridge.src.core.bridge_orchestrator.SignalManager") as MockSignalManager, \
         patch("simulation_bridge.src.core.bridge_orchestrator.BridgeCore") as MockBridgeCore, \
         patch("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates"), \
         patch("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config") as mock_proto_conf:

        # Simula una configurazione protocollo con segnali
        mock_proto_conf.return_value = {
            "mqtt": {
                "class": "mqtt_adapter.MQTTAdapter",
                "enabled": True,
                "signals": {
                    "on_message": "MQTTAdapter.on_message"
                }
            }
        }
        MockSignalManager.get_enabled_protocols.return_value = ["mqtt"]
        MockSignalManager.register_adapter_instance.return_value = None
        MockSignalManager.set_bridge_core.return_value = None
        MockSignalManager.connect_all_signals.return_value = None

        # Simula importlib per l'adapter
        with patch("importlib.import_module") as mock_import:
            mock_adapter_class = MagicMock()
            mock_import.return_value = MagicMock(MQTTAdapter=mock_adapter_class)
            orchestrator = BridgeOrchestrator()
            orchestrator.config_manager = mock_config_manager
            orchestrator.protocol_config = mock_proto_conf.return_value
            orchestrator.adapter_classes = {"mqtt": mock_adapter_class}
            orchestrator.setup_interfaces()

            # Verifica che SignalManager sia stato usato per registrare e connettere segnali
            MockSignalManager.register_adapter_instance.assert_called_with("mqtt", mock_adapter_class(mock_config_manager))
            MockSignalManager.set_bridge_core.assert_called()
            MockSignalManager.connect_all_signals.assert_called()

def test_signal_manager_register_and_resolve_callback(monkeypatch):
    # Usa SignalManager reale, ma patcha logger e config
    class DummyAdapter:
        def on_message(self): pass

    dummy_adapter = DummyAdapter()
    protocol = "dummy"
    func_path = "DummyAdapter.on_message"

    # Patch PROTOCOL_CONFIG per includere il protocollo dummy
    monkeypatch.setattr(SignalManager, "PROTOCOL_CONFIG", {
        "dummy": {
            "enabled": True,
            "signals": {"on_message": func_path}
        }
    })
    SignalManager.register_adapter_instance(protocol, dummy_adapter)
    callback = SignalManager._resolve_callback(func_path, protocol)
    assert callback == dummy_adapter.on_message

    # Test che get_enabled_protocols ritorni il protocollo dummy
    enabled = SignalManager.get_enabled_protocols()
    assert "dummy" in enabled

    # Test che get_available_signals ritorni il segnale
    signals = SignalManager.get_available_signals("dummy")
    assert "on_message" in signals

    # Test che is_protocol_enabled ritorni True
    assert SignalManager.is_protocol_enabled("dummy")

def test_signal_manager_connect_and_disconnect(monkeypatch):
    # Usa SignalManager reale, patcha logger e config
    class DummyAdapter:
        def on_message(self): pass

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

    # Patch _resolve_callback per restituire il metodo corretto
    monkeypatch.setattr(SignalManager, "_resolve_callback", lambda func_path, protocol: dummy_adapter.on_message)

    # Connect e disconnect non devono sollevare eccezioni
    SignalManager.connect_all_signals()
    SignalManager.disconnect_all_signals()

def test_bridge_orchestrator_init_calls_ensure_certificates(monkeypatch):
    called = {}
    def fake_ensure_certificates(**kwargs):
        called['called'] = True
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates", fake_ensure_certificates)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ConfigManager", MagicMock())
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config", lambda: {})
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes", lambda self: {})
    BridgeOrchestrator()
    assert called.get('called')

def test_bridge_orchestrator_init_ensure_certificates_exception(monkeypatch):
    def fake_ensure_certificates(**kwargs):
        raise RuntimeError("Cert error")
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates", fake_ensure_certificates)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ConfigManager", MagicMock())
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config", lambda: {})
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes", lambda self: {})
    with pytest.raises(RuntimeError, match="Cert error"):
        BridgeOrchestrator()

def test_bridge_orchestrator_init_certificates_custom_days(monkeypatch):
    params = {}
    def fake_ensure_certificates(**kwargs):
        params.update(kwargs)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates", fake_ensure_certificates)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ConfigManager", MagicMock())
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config", lambda: {})
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes", lambda self: {})
    BridgeOrchestrator()
    assert params.get("validity_days") == 365

def test_bridge_orchestrator_start_and_stop(monkeypatch, mock_config_manager):
    """Test che start e stop chiamino SignalManager.disconnect_all_signals e stop sugli adapter."""
    monkeypatch.setattr("simulation_bridge.src.utils.certs.ensure_certificates", lambda **kwargs: None)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ConfigManager", lambda *a, **k: mock_config_manager)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config", lambda: {})
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes", lambda self: {})
    orchestrator = BridgeOrchestrator()
    orchestrator.adapters = {"mqtt": MagicMock(), "rest": MagicMock()}
    with patch("simulation_bridge.src.utils.signal_manager.SignalManager.disconnect_all_signals") as disconnect_mock:
        orchestrator.stop()
        disconnect_mock.assert_called_once()
        for adapter in orchestrator.adapters.values():
            adapter.stop.assert_called_once()

def test_bridge_orchestrator_logs_bridge_id(monkeypatch, caplog):
    # Verifica che venga loggato l'ID del bridge all'inizializzazione
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates", lambda **kwargs: None)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ConfigManager", lambda *a, **k: MagicMock(get_config=lambda: {'simulation_bridge': {'bridge_id': 'test-bridge'}, 'rabbitmq': {}}))
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config", lambda: {})
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes", lambda self: {})
    with caplog.at_level(logging.INFO):
        BridgeOrchestrator()
    assert "Simulation bridge ID: test-bridge" in caplog.text

def test_bridge_orchestrator_logs_enabled_protocols(monkeypatch, caplog):
    # Verifica che venga loggato l'elenco dei protocolli abilitati
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates", lambda **kwargs: None)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ConfigManager", lambda *a, **k: MagicMock(get_config=lambda: {'simulation_bridge': {'bridge_id': 'test-bridge'}, 'rabbitmq': {}}))
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config", lambda: {"mqtt": {"class": "mqtt_adapter.MQTTAdapter", "enabled": True}})
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes", lambda self: {"mqtt": MagicMock(return_value=MagicMock())})
    with patch("simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure") as MockInfra, \
         patch("simulation_bridge.src.core.bridge_orchestrator.SignalManager") as MockSignalManager, \
         patch("simulation_bridge.src.core.bridge_orchestrator.BridgeCore"):
        MockSignalManager.get_enabled_protocols.return_value = ["mqtt"]
        MockSignalManager.register_adapter_instance.return_value = None
        MockSignalManager.set_bridge_core.return_value = None
        MockSignalManager.connect_all_signals.return_value = None
        orchestrator = BridgeOrchestrator()
        with caplog.at_level(logging.INFO):
            orchestrator.setup_interfaces()
        assert "Enabled protocols: MQTT" in caplog.text

def test_bridge_orchestrator_logs_no_enabled_protocols(monkeypatch, caplog):
    # Verifica che venga loggato un warning se nessun protocollo è abilitato
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates", lambda **kwargs: None)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ConfigManager", lambda *a, **k: MagicMock(get_config=lambda: {'simulation_bridge': {'bridge_id': 'test-bridge'}, 'rabbitmq': {}}))
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config", lambda: {"mqtt": {"class": "mqtt_adapter.MQTTAdapter", "enabled": False}})
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes", lambda self: {"mqtt": MagicMock(return_value=MagicMock())})
    with patch("simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure") as MockInfra, \
         patch("simulation_bridge.src.core.bridge_orchestrator.SignalManager") as MockSignalManager, \
         patch("simulation_bridge.src.core.bridge_orchestrator.BridgeCore"):
        MockSignalManager.get_enabled_protocols.return_value = []
        orchestrator = BridgeOrchestrator()
        with caplog.at_level(logging.WARNING):
            orchestrator.setup_interfaces()
        assert "No protocol adapters are enabled" in caplog.text

def test_bridge_orchestrator_logs_error_on_exception(monkeypatch, caplog):
    # Verifica che venga loggato un errore se setup_interfaces solleva un'eccezione
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates", lambda **kwargs: None)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ConfigManager", lambda *a, **k: MagicMock(get_config=lambda: {'simulation_bridge': {'bridge_id': 'test-bridge'}, 'rabbitmq': {}}))
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config", lambda: {})
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes", lambda self: {})
    with patch("simulation_bridge.src.core.bridge_orchestrator.RabbitMQInfrastructure", side_effect=Exception("fail")):
        orchestrator = BridgeOrchestrator()
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception):
                orchestrator.setup_interfaces()
        assert "Error setting up interfaces: fail" in caplog.text

def test_bridge_orchestrator_certificates_validation_valid(monkeypatch, tmp_path):
    """Test that bridge orchestrator works with valid existing certificates."""
    from simulation_bridge.src.utils.certs import CertificateGenerator
    
    # Create valid certificates
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    generator = CertificateGenerator()
    success, _ = generator.generate_certificate_pair(str(cert_path), str(key_path))
    assert success
    
    # Mock ensure_certificates to use our test paths
    def mock_ensure_certificates(**kwargs):
        kwargs['cert_path'] = str(cert_path)
        kwargs['key_path'] = str(key_path)
        # Call real function with test paths
        from simulation_bridge.src.utils.certs import ensure_certificates as real_ensure
        real_ensure(**kwargs)
    
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates", mock_ensure_certificates)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ConfigManager", lambda *a, **k: MagicMock(get_config=lambda: {'simulation_bridge': {'bridge_id': 'test-bridge'}, 'rabbitmq': {}}))
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config", lambda: {})
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes", lambda self: {})
    
    # Should not raise exception
    BridgeOrchestrator()

def test_bridge_orchestrator_certificates_validation_expired(monkeypatch, tmp_path, caplog):
    """Test that bridge orchestrator regenerates expired certificates."""
    from simulation_bridge.src.utils.certs import CertificateGenerator
    import datetime
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    
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
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    
    def mock_ensure_certificates(**kwargs):
        kwargs['cert_path'] = str(cert_path)
        kwargs['key_path'] = str(key_path)
        from simulation_bridge.src.utils.certs import ensure_certificates as real_ensure
        real_ensure(**kwargs)
    
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates", mock_ensure_certificates)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ConfigManager", lambda *a, **k: MagicMock(get_config=lambda: {'simulation_bridge': {'bridge_id': 'test-bridge'}, 'rabbitmq': {}}))
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config", lambda: {})
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes", lambda self: {})
    
    with caplog.at_level(logging.ERROR):
        BridgeOrchestrator()
    assert "Existing certificates are invalid" in caplog.text

def test_bridge_orchestrator_certificates_missing_files(monkeypatch, tmp_path, caplog):
    """Test that bridge orchestrator generates certificates when files are missing."""
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    
    def mock_ensure_certificates(**kwargs):
        kwargs['cert_path'] = str(cert_path)
        kwargs['key_path'] = str(key_path)
        from simulation_bridge.src.utils.certs import ensure_certificates as real_ensure
        real_ensure(**kwargs)
    
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates", mock_ensure_certificates)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ConfigManager", lambda *a, **k: MagicMock(get_config=lambda: {'simulation_bridge': {'bridge_id': 'test-bridge'}, 'rabbitmq': {}}))
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config", lambda: {})
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes", lambda self: {})
    
    with caplog.at_level(logging.INFO):
        BridgeOrchestrator()
    assert "SSL certificates generated successfully" in caplog.text
    assert cert_path.exists()
    assert key_path.exists()

def test_bridge_orchestrator_certificates_corrupted_files(monkeypatch, tmp_path, caplog):
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
    
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates", mock_ensure_certificates)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ConfigManager", lambda *a, **k: MagicMock(get_config=lambda: {'simulation_bridge': {'bridge_id': 'test-bridge'}, 'rabbitmq': {}}))
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config", lambda: {})
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes", lambda self: {})
    
    with caplog.at_level(logging.ERROR):
        BridgeOrchestrator()
    assert "Existing certificates are invalid" in caplog.text

def test_bridge_orchestrator_certificates_permission_error(monkeypatch, tmp_path):
    """Test that bridge orchestrator handles permission errors during certificate generation."""
    cert_path = tmp_path / "readonly" / "cert.pem"
    key_path = tmp_path / "readonly" / "key.pem"
    
    def mock_ensure_certificates(**kwargs):
        # Simulate permission error without actually creating read-only files
        raise RuntimeError("Certificate generation failed: [Errno 13] Permission denied: '/test/path/cert.pem'")
    
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ensure_certificates", mock_ensure_certificates)
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.ConfigManager", lambda *a, **k: MagicMock(get_config=lambda: {'simulation_bridge': {'bridge_id': 'test-bridge'}, 'rabbitmq': {}}))
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.load_protocol_config", lambda: {})
    monkeypatch.setattr("simulation_bridge.src.core.bridge_orchestrator.BridgeOrchestrator._import_adapter_classes", lambda self: {})
    
    with pytest.raises(RuntimeError, match="Certificate generation failed"):
        BridgeOrchestrator()

def test_logger_setup_and_get_logger(tmp_path, caplog):
    """Test setup_logger creates file and console handlers, and get_logger returns the same instance."""
    import os
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
    monkeypatch.setattr(logger_mod.colorlog, "ColoredFormatter", fake_colored_formatter)

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
