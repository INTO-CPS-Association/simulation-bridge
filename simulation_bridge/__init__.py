"""Convenience utilities for the Simulation Bridge package."""
from .src.protocol_adapters.inmemory.inmemory_adapter import InMemoryAdapter
from .src.protocol_adapters.rabbitmq.rabbitmq_adapter import RabbitMQAdapter
from .src.utils.config_manager import ConfigManager
from .src.utils.signal_manager import SignalManager
from .src.core.bridge_core import BridgeCore


class DummyAdapter:
    """Adapter neutro: serve solo per zittire SignalManager su mqtt/rest."""
    # metodi citati nel file adapters_signal.json

    def publish_result_message_mqtt(self, *_, **__):
        pass

    def publish_result_message_rest(self, *_, **__):
        pass

    # chiamati dal bridge quando avvia/ferma gli adapter
    def start(self):
        pass

    def stop(self):
        pass


class InMemorySimulation:
    """Run simulations using the in-memory protocol adapter."""

    def __init__(self, config_path: str | None = None) -> None:
        self.config_manager = ConfigManager(config_path)
        self.inmemory_adapter = InMemoryAdapter(self.config_manager)
        self.rabbitmq_adapter = RabbitMQAdapter(self.config_manager)

        self.bridge = BridgeCore(
            self.config_manager,
            {
                "inmemory": self.inmemory_adapter,
                "rabbitmq": self.rabbitmq_adapter,
            },
        )

        # --- registriamo tutti gli adapter necessari ---
        SignalManager.set_bridge_core(self.bridge)
        SignalManager.register_adapter_instance(
            "inmemory", self.inmemory_adapter)
        SignalManager.register_adapter_instance(
            "rabbitmq", self.rabbitmq_adapter)

        dummy = DummyAdapter()
        SignalManager.register_adapter_instance("mqtt", dummy)
        SignalManager.register_adapter_instance("rest", dummy)

        # colleghiamo i segnali *dopo* aver registrato gli adapter
        SignalManager.connect_all_signals()

        # avvio degli unici adapter “veri”
        self.inmemory_adapter.start()
        self.rabbitmq_adapter.start()

    def send(self, message, callback) -> None:
        """Send a message and register a callback for the result."""
        self.inmemory_adapter.send(message, callback)

    def stop(self) -> None:
        """Stop the simulation and disconnect signals."""
        self.inmemory_adapter.stop()
        self.rabbitmq_adapter.stop()
        SignalManager.disconnect_all_signals()


__all__ = ["InMemoryAdapter", "InMemorySimulation"]
