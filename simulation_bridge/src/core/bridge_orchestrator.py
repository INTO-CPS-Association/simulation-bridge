"""Bridge Orchestrator module for simulation bridge."""
import time
import importlib
import threading
from .bridge_core import BridgeCore
from .bridge_infrastructure import RabbitMQInfrastructure
from ..utils.config_manager import ConfigManager
from ..utils.config_loader import load_protocol_config
from ..utils.logger import get_logger
from ..utils.signal_manager import SignalManager
from ..utils.certs import ensure_certificates
from ..utils.performance_monitor import PerformanceMonitor

# Constants for RabbitMQ connection parameters
POLL_INTERVAL_SECONDS = 60  # Continuously check adapter status every 60 seconds

logger = get_logger()

# pylint: disable=too-many-instance-attributes


class BridgeOrchestrator:
    """Orchestrates the simulation bridge components and lifecycle."""

    def __init__(self, config_path: str = None):
        """Initialize the bridge orchestrator.

        Args:
            simulation_bridge_id: Unique identifier for this bridge instance
            config_path: Optional path to configuration file
        """
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.get_config()
        PerformanceMonitor(config=self.config)
        self.simulation_bridge_id = self.config['simulation_bridge']['bridge_id']
        logger.info("Simulation bridge ID: %s", self.simulation_bridge_id)
        # Validate and ensure SSL certificates are present
        ensure_certificates(validity_days=365)

        self.bridge = None
        self.adapters = {}
        self._running = False

        self.protocol_config = load_protocol_config()
        self.adapter_classes = self._import_adapter_classes()

    def setup_interfaces(self):
        """Set up all communication interfaces and the core bridge.

        This method initializes infrastructure (e.g., RabbitMQ), creates adapter
        instances for each protocol (e.g., MQTT, REST), registers them with the
        SignalManager, and connects all defined signals to their respective
        callbacks.
        """
        try:
            # Set up RabbitMQ infrastructure
            logger.debug("Setting up RabbitMQ infrastructure...")
            infrastructure = RabbitMQInfrastructure(self.config_manager)
            infrastructure.setup()

            # Get list of enabled protocols
            enabled_protocols = SignalManager.get_enabled_protocols()
            if not enabled_protocols:
                logger.warning(
                    "No protocol adapters are enabled — no messages will be received.")
            else:
                protocols_str = ", ".join(proto.upper()
                                          for proto in enabled_protocols)
                logger.info("Enabled protocols: %s", protocols_str)

            # Instantiate and register each adapter only for enabled protocols
            for name, adapter_class in self.adapter_classes.items():
                if name not in enabled_protocols:
                    logger.debug(
                        "Skipping initialization of disabled protocol: %s",
                        name.upper())
                    continue

                adapter = adapter_class(self.config_manager)
                self.adapters[name] = adapter

                # Register the adapter instance with SignalManager
                SignalManager.register_adapter_instance(name, adapter)
                logger.info("%s Adapter initialized correctly", name.upper())

            # Create and register the core bridge component
            self.bridge = BridgeCore(self.config_manager, self.adapters)
            SignalManager.set_bridge_core(self.bridge)

            # Connect all signals defined in protocol config (only for enabled
            # protocols)
            SignalManager.connect_all_signals()
            logger.info(
                "Bridge core initialized and signals connected for enabled protocols")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error setting up interfaces: %s", exc)
            raise

    def _start_adapters_async(self):
        """Start all adapters in separate threads."""
        for name, adapter in self.adapters.items():
            thread = threading.Thread(
                target=adapter.start,
                name=f"{name}_adapter_thread",
                daemon=True)
            thread.start()
            logger.debug("Started adapter %s in thread %s", name, thread.name)

    def start(self):
        """Start the bridge and all its components."""
        # 1) Initial setup
        self.setup_interfaces()
        try:
            # 2) Start all adapters
            for adapter in self.adapters.values():
                adapter.start()
            logger.info("Simulation Bridge Running")
            self._running = True
            # 3) Polling loop
            while self._running:
                all_alive = all(
                    adapter.is_running for adapter in self.adapters.values())
                if not all_alive:
                    logger.error(
                        "One or more adapters have stopped unexpectedly")
                    break
                time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            # 4) Handle user Ctrl+C
            logger.info("Shutdown requested by user (Ctrl+C)")
            self._running = False
            raise SystemExit
        finally:
            # 5) In any case (adapter error or Ctrl+C), stop everything
            self.stop()
        raise SystemExit("Simulation Bridge stopped")

    def stop(self):
        """Stop all components of the bridge cleanly."""
        logger.debug("Stopping all components...")
        self._running = False
        try:
            for name, adapter in self.adapters.items():
                try:
                    adapter.stop()
                    # Join thread only if the adapter has a thread attribute
                    if hasattr(adapter, 'thread'):
                        adapter.thread.join()
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.error("Error stopping %s adapter: %s", name, exc)
            SignalManager.disconnect_all_signals()
            logger.info("Simulation Bridge Stopped")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error during shutdown: %s", exc)

    def _import_adapter_classes(self):
        """
        For each protocol specified in the loaded protocol configuration,
        it extracts the full class path, imports the module relative to the
        protocol_adapters package, retrieves the class object,
        and stores it keyed by the protocol name.
        """
        classes = {}
        for protocol, data in self.protocol_config.items():
            class_path = data.get("class")
            module_name, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(
                module_name,
                package="simulation_bridge.src.protocol_adapters")
            adapter_class = getattr(module, class_name)
            classes[protocol] = adapter_class
        return classes
