from .bridge_core import BridgeCore
from ..protocol_adapters.rabbitmq.rabbitmq_adapter import RabbitMQAdapter
from ..protocol_adapters.mqtt.mqtt_adapter import MQTTAdapter
from ..protocol_adapters.rest.rest_adapter import RESTAdapter
from .bridge_infrastructure import RabbitMQInfrastructure
from ..utils.config_manager import ConfigManager
from ..utils.logger import get_logger

logger = get_logger()


class BridgeOrchestrator:
    def __init__(self, simulation_bridge_id: str, config_path: str = None):
        self.simulation_bridge_id = simulation_bridge_id
        logger.info(f"Simulation bridge ID: {self.simulation_bridge_id}")

        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.get_config()

        self.bridge = None
        self.adapters = {}
        self._running = False

        # Adapter class registry
        self.adapter_classes = {
            'rabbitmq': RabbitMQAdapter,
            'mqtt': MQTTAdapter,
            'rest': RESTAdapter,
        }

    def setup_interfaces(self):
        try:
            logger.debug("Setting up RabbitMQ infrastructure...")
            infrastructure = RabbitMQInfrastructure(self.config_manager)
            infrastructure.setup()

            for name, adapter_class in self.adapter_classes.items():
                adapter = adapter_class(self.config_manager)
                self.adapters[name] = adapter
                logger.info(f"{name.upper()} Adapter initialized correctly")

            self.bridge = BridgeCore(self.config_manager, self.adapters)
            logger.info("Bridge core initialized")

        except Exception as e:
            logger.error(f"Error setting up interfaces: {e}")
            raise

    def start(self):
        try:
            self.setup_interfaces()
            # Start each adapter
            for adapter in self.adapters.values():
                adapter.start()
            logger.debug("All adapters started")
            logger.info("Simulation Bridge Running")

            self._running = True

            while self._running:
                if not all(
                        adapter.is_running for adapter in self.adapters.values()):
                    logger.error("One or more adapters have stopped")
                    break
                import time
                time.sleep(1)

        except Exception as e:
            logger.error(f"Error in start: {e}")
            self.stop()
            raise

    def stop(self):
        self._running = False
        try:
            for name, adapter in self.adapters.items():
                try:
                    adapter.stop()
                except Exception as e:
                    logger.error(f"Error stopping {name} adapter: {e}")
            if self.bridge:
                self.bridge.stop()
            logger.info("All components stopped")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
