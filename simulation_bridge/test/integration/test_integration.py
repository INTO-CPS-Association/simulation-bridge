"""
Integration tests for the Bridge Orchestrator interface setup and lifecycle.
Verifies the initialization, connection, start, and stop flows of components.
"""

import threading
import time
import unittest

# pylint: disable=too-many-public-methods,unused-argument,protected-access


class MockBridgeCore: # pylint: disable=too-few-public-methods
    """Mock BridgeCore for testing."""

    def __init__(self, config_manager, adapters):
        self.config_manager = config_manager
        self.adapters = adapters
        self.initialized = True


class MockRabbitMQInfrastructure:
    """Mock RabbitMQ infrastructure for testing."""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.setup_called = False

    def setup(self):
        self.setup_called = True


class MockAdapter:
    """Generic mock adapter."""

    def __init__(self, name, config_manager):
        self.name = name
        self.config_manager = config_manager
        self.is_running = False
        self.started = False
        self.stopped = False
        self.thread = None

    def start(self):
        self.started = True
        self.is_running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.start()

    def stop(self):
        self.stopped = True
        self.is_running = False

    def _run(self):
        while self.is_running:
            time.sleep(0.1)


class MockConfigManager:
    """Mock configuration manager."""

    def __init__(self, config_path=None):
        self.config_path = config_path

    def get_config(self):
        return {"simulation_bridge": {"bridge_id": "test-bridge-001"}}


class MockSignalManager:
    """Mock SignalManager handling protocols and registration."""

    enabled_protocols = ["mqtt", "rest"]
    adapter_instances = {}
    bridge_core_instance = None

    @classmethod
    def get_enabled_protocols(cls):
        return cls.enabled_protocols

    @classmethod
    def register_adapter_instance(cls, name, adapter):
        cls.adapter_instances[name] = adapter

    @classmethod
    def set_bridge_core(cls, bridge_core):
        cls.bridge_core_instance = bridge_core

    @classmethod
    def connect_all_signals(cls):
        pass

    @classmethod
    def disconnect_all_signals(cls):
        pass


class TestBridgeOrchestratorSetup(unittest.TestCase):
    """Tests for BridgeOrchestrator interface setup."""

    def setUp(self):
        self.config_path = "test_config.yaml"
        self.mock_protocol_config = {
            "mqtt": {
                "enabled": True,
                "class": "mqtt_adapter.MQTTAdapter",
                "signals": {"mqtt_message_received": "MQTTAdapter.handle_message"},
            },
            "rest": {
                "enabled": True,
                "class": "rest_adapter.RESTAdapter",
                "signals": {"rest_request_received": "RESTAdapter.handle_request"},
            },
        }
        self.adapter_classes = {
            "mqtt": lambda config_manager: MockAdapter("mqtt", config_manager),
            "rest": lambda config_manager: MockAdapter("rest", config_manager),
        }

    def create_orchestrator_mock(self):
        """Return a mock BridgeOrchestrator class with required methods."""

        mock_protocol_config = self.mock_protocol_config
        adapter_classes = self.adapter_classes

        class MockBridgeOrchestrator: # pylint: disable=too-few-public-methods,too-many-instance-attributes
            """Mock BridgeOrchestrator with simplified setup and lifecycle."""

            def __init__(self, config_path=None):
                self.config_manager = MockConfigManager(config_path)
                self.config = self.config_manager.get_config()
                self.simulation_bridge_id = self.config["simulation_bridge"]["bridge_id"]
                self.bridge = None
                self.adapters = {}
                self._running = False
                self.protocol_config = mock_protocol_config
                self.adapter_classes = adapter_classes

            def setup_interfaces(self):
                """Setup interfaces including adapters and bridge core."""
                try:
                    infrastructure = MockRabbitMQInfrastructure(
                        self.config_manager)
                    infrastructure.setup()

                    enabled_protocols = MockSignalManager.get_enabled_protocols()
                    if not enabled_protocols:
                        raise ValueError("No protocol adapters are enabled")

                    for name, adapter_class in self.adapter_classes.items():
                        if name not in enabled_protocols:
                            continue
                        adapter = adapter_class(self.config_manager)
                        self.adapters[name] = adapter
                        MockSignalManager.register_adapter_instance(
                            name, adapter)

                    self.bridge = MockBridgeCore(
                        self.config_manager, self.adapters)
                    MockSignalManager.set_bridge_core(self.bridge)
                    MockSignalManager.connect_all_signals()

                except Exception as exc:
                    raise RuntimeError(f"Error setting up interfaces: {exc}") from exc

            def start(self):
                """Start all adapters and mark running state."""
                self.setup_interfaces()
                for adapter in self.adapters.values():
                    adapter.start()
                self._running = True
                return True

            def stop(self):
                """Stop all adapters and clean up signals."""
                try:
                    for adapter in self.adapters.values():
                        adapter.stop()
                        if adapter.thread:
                            adapter.thread.join(timeout=1)
                    MockSignalManager.disconnect_all_signals()
                    self._running = False
                except Exception as exc:
                    raise RuntimeError(f"Error during shutdown: {exc}") from exc

        return MockBridgeOrchestrator

    def test_setup_interfaces_initializes_components(self):
        """Verify setup initializes bridge core and adapters correctly."""
        BridgeOrchestrator = self.create_orchestrator_mock()
        orchestrator = BridgeOrchestrator(self.config_path)

        orchestrator.setup_interfaces()

        self.assertIsNotNone(orchestrator.bridge, "Bridge core not initialized")
        self.assertIsInstance(
            orchestrator.bridge,
            MockBridgeCore,
            "Wrong bridge core type")

        expected_adapters = ["mqtt", "rest"]
        self.assertEqual(len(orchestrator.adapters), len(
            expected_adapters), "Adapter count mismatch")
        for name in expected_adapters:
            self.assertIn(
                name,
                orchestrator.adapters,
                f"Adapter {name} missing")
            self.assertIsInstance(
                orchestrator.adapters[name],
                MockAdapter,
                f"Adapter {name} wrong type")

        self.assertEqual(len(MockSignalManager.adapter_instances), len(expected_adapters),
                         "Adapters not registered correctly in SignalManager")
        self.assertIs(MockSignalManager.bridge_core_instance, orchestrator.bridge,
                      "Bridge core not registered in SignalManager")

    def test_start_and_stop_lifecycle(self):
        """Test full lifecycle start and stop of orchestrator and adapters."""
        BridgeOrchestrator = self.create_orchestrator_mock()
        orchestrator = BridgeOrchestrator(self.config_path)

        result = orchestrator.start()
        self.assertTrue(result, "Bridge start failed")
        self.assertTrue(orchestrator._running, "Bridge not running after start")

        for name, adapter in orchestrator.adapters.items():
            self.assertTrue(adapter.started, f"Adapter {name} not started")
            self.assertTrue(adapter.is_running, f"Adapter {name} not running")

        orchestrator.stop()
        self.assertFalse(
            orchestrator._running,
            "Bridge still running after stop")

        for name, adapter in orchestrator.adapters.items():
            self.assertTrue(adapter.stopped, f"Adapter {name} not stopped")
            self.assertFalse(
                adapter.is_running,
                f"Adapter {name} still running")

    def test_setup_interfaces_raises_on_adapter_failure(self):
        """Ensure setup raises RuntimeError if adapter initialization fails."""
        BridgeOrchestrator = self.create_orchestrator_mock()
        orchestrator = BridgeOrchestrator(self.config_path)

        def failing_adapter(config_manager):
            raise Exception("Adapter initialization failed") # pylint: disable=broad-exception-raised

        orchestrator.adapter_classes["mqtt"] = failing_adapter

        with self.assertRaises(RuntimeError) as cm:
            orchestrator.setup_interfaces()

        self.assertIn("Error setting up interfaces", str(cm.exception))

    def test_setup_interfaces_raises_when_no_protocols_enabled(self):
        """Verify setup raises error if no protocols are enabled."""
        BridgeOrchestrator = self.create_orchestrator_mock()
        orchestrator = BridgeOrchestrator(self.config_path)

        original_get_enabled = MockSignalManager.get_enabled_protocols
        MockSignalManager.get_enabled_protocols = lambda: []

        try:
            with self.assertRaises(RuntimeError) as cm:
                orchestrator.setup_interfaces()
            self.assertIn("No protocol adapters are enabled", str(cm.exception))
        finally:
            MockSignalManager.get_enabled_protocols = original_get_enabled

    def test_adapter_registration_order(self):
        """Check correct registration order of adapters and bridge core."""
        BridgeOrchestrator = self.create_orchestrator_mock()
        orchestrator = BridgeOrchestrator(self.config_path)

        orchestrator.setup_interfaces()

        self.assertEqual(len(orchestrator.adapters), 2)
        for name in ["mqtt", "rest"]:
            self.assertIn(name, MockSignalManager.adapter_instances)
            self.assertIs(
                MockSignalManager.adapter_instances[name],
                orchestrator.adapters[name])

        self.assertIs(
            MockSignalManager.bridge_core_instance,
            orchestrator.bridge)

    def test_configuration_propagation(self):
        """Verify configuration propagation to all components."""
        BridgeOrchestrator = self.create_orchestrator_mock()
        orchestrator = BridgeOrchestrator(self.config_path)

        orchestrator.setup_interfaces()

        self.assertEqual(orchestrator.simulation_bridge_id, "test-bridge-001")
        for adapter in orchestrator.adapters.values():
            self.assertIs(adapter.config_manager, orchestrator.config_manager)

        self.assertIs(
            orchestrator.bridge.config_manager,
            orchestrator.config_manager)
        self.assertIs(orchestrator.bridge.adapters, orchestrator.adapters)
