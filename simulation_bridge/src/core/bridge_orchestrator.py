"""Bridge Orchestrator module for simulation bridge."""
import time
import importlib
from .bridge_core import BridgeCore
from .bridge_infrastructure import RabbitMQInfrastructure
from ..utils.config_manager import ConfigManager
from ..utils.config_loader import load_protocol_config
from ..utils.logger import get_logger

logger = get_logger()


class BridgeOrchestrator:
    """Orchestrates the simulation bridge components and lifecycle."""

    def __init__(self, simulation_bridge_id: str, config_path: str = None):
        """Initialize the bridge orchestrator.

        Args:
            simulation_bridge_id: Unique identifier for this bridge instance
            config_path: Optional path to configuration file
        """
        self.simulation_bridge_id = simulation_bridge_id
        logger.info("Simulation bridge ID: %s", self.simulation_bridge_id)

        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.get_config()

        self.bridge = None
        self.adapters = {}
        self._running = False

        self.protocol_config = load_protocol_config()
        self.adapter_classes = self._import_adapter_classes()

    def setup_interfaces(self):
        """Set up all communication interfaces and the core bridge."""
        try:
            logger.debug("Setting up RabbitMQ infrastructure...")
            infrastructure = RabbitMQInfrastructure(self.config_manager)
            infrastructure.setup()

            for name, adapter_class in self.adapter_classes.items():
                adapter = adapter_class(self.config_manager)
                self.adapters[name] = adapter
                logger.info("%s Adapter initialized correctly", name.upper())

            self.bridge = BridgeCore(self.config_manager, self.adapters)
            logger.info("Bridge core initialized")

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error setting up interfaces: %s", exc)
            raise

    def start(self):
        """Start the bridge and all its components."""
        # 1) Initial setup
        self.setup_interfaces()

        # 2) Start all adapters
        for adapter in self.adapters.values():
            adapter.start()
        logger.info("Simulation Bridge Running")
        self._running = True
        try:
            # 3) Polling loop
            while True:
                all_alive = all(
                    adapter.is_running for adapter in self.adapters.values())
                if not all_alive:
                    logger.error(
                        "One or more adapters have stopped unexpectedly")
                    break
                time.sleep(1)

        except KeyboardInterrupt:
            # 4) Handle user Ctrl+C
            logger.info("Shutdown requested by user (Ctrl+C)")

        finally:
            # 5) In any case (adapter error or Ctrl+C), stop everything
            self.stop()

    def stop(self):
        """Stop all components of the bridge cleanly."""
        logger.debug("Stopping all components...")
        try:
            for name, adapter in self.adapters.items():
                try:
                    adapter.stop()
                    # Join thread only if the adapter has a thread attribute
                    if hasattr(adapter, 'thread'):
                        adapter.thread.join()
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.error("Error stopping %s adapter: %s", name, exc)

            if self.bridge:
                self.bridge.stop()
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
