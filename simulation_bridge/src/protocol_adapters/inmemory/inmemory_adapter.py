from __future__ import annotations
from typing import Dict, Any, Callable

from blinker import signal

from ...utils.config_manager import ConfigManager
from ...utils.logger import get_logger
from ..base.protocol_adapter import ProtocolAdapter
from ...utils.signal_manager import SignalManager
from ...core.bridge_core import BridgeCore
from ..rabbitmq.rabbitmq_adapter import RabbitMQAdapter


logger = get_logger()


class InMemoryAdapter(ProtocolAdapter):
    """Simple in-memory protocol adapter."""

    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        self._callbacks: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self._pending: Dict[str, list[Dict[str, Any]]] = {}

    def send(self, message: Dict[str, Any],
             callback: Callable[[Dict[str, Any]], None]) -> None:
        req_id = message.get("simulation", {}).get("request_id")
        if not req_id:
            logger.warning("InMemory - missing request_id in message")
            return
        # Register the callback for this request_id
        self._callbacks[req_id] = callback
        # If the request_id is already in pending, we need to
        # immediately call the callback for all pending messages.
        if req_id in self._pending:
            for msg in self._pending.pop(req_id):
                callback(msg)

        signal("message_received_input_inmemory").send(
            message=message,
            producer=message["simulation"].get("client_id", "unknown"),
            consumer=message["simulation"].get("simulator", "unknown"),
            protocol="inmemory",
        )

    def _handle_result(self, sender, **kwargs):      # pylint: disable=unused-argument
        msg = kwargs.get("message", {})
        req_id = msg.get("request_id")
        status = msg.get("status", "").lower()

        cb = self._callbacks.get(req_id)
        if cb:
            try:
                cb(msg)
            except Exception as exc:
                logger.error("InMemory - error in callback: %s", exc)

            if status in {"completed", "failed", "error",
                          "aborted", "cancelled"}:
                self._callbacks.pop(req_id, None)
        else:
            # no callback registered for this request_id,
            # cache the message for later processing
            self._pending.setdefault(req_id, []).append(msg)
            logger.debug(
                "InMemory - cached %s msg for request_id %s "
                "(callback not yet registered)",
                status or "unknown-status", req_id
            )

    def _get_config(self) -> Dict[str, Any]:
        return {}

    def start(self) -> None:
        logger.debug("InMemory adapter started")
        self._running = True

    def stop(self) -> None:
        logger.debug("InMemory adapter stopped")
        self._running = False

    def _handle_message(self, message: Dict[str, Any]) -> None:  # pylint: disable=unused-argument
        """Not used for in-memory adapter."""
        pass


class DummyAdapter(ProtocolAdapter):
    """Neutral adapter for MQTT and REST protocols."""

    def __init__(self, config_manager: ConfigManager | None = None):
        super().__init__(config_manager or ConfigManager(None))

    def _get_config(self) -> Dict[str, Any]:
        return {}

    def start(self) -> None:
        logger.debug("DummyAdapter started (no-op)")
        self._running = True

    def stop(self) -> None:
        logger.debug("DummyAdapter stopped (no-op)")
        self._running = False

    def _handle_message(self, message: Dict[str, Any]) -> None:  # noqa: D401
        pass

    def publish_result_message_mqtt(self, *_, **__) -> None:
        pass

    def publish_result_message_rest(self, *_, **__) -> None:
        pass


class InMemorySimulation:
    """Run simulations using the in-memory protocol adapter."""

    def __init__(self, config_path: str | None = None) -> None:
        self.config_manager = ConfigManager(config_path)
        self.inmemory_adapter = InMemoryAdapter(self.config_manager)
        self.rabbitmq_adapter = RabbitMQAdapter(self.config_manager)

        self.bridge = BridgeCore(
            self.config_manager,
            {"inmemory": self.inmemory_adapter,
             "rabbitmq": self.rabbitmq_adapter},
        )

        SignalManager.set_bridge_core(self.bridge)
        SignalManager.register_adapter_instance(
            "inmemory", self.inmemory_adapter)
        SignalManager.register_adapter_instance(
            "rabbitmq", self.rabbitmq_adapter)

        # Required to satisfy signals expecting these adapters.
        # Acts as a "null object" to avoid errors when MQTT/REST are unused.
        dummy = DummyAdapter()
        SignalManager.register_adapter_instance("mqtt", dummy)
        SignalManager.register_adapter_instance("rest", dummy)

        SignalManager.connect_all_signals()

        self.inmemory_adapter.start()
        self.rabbitmq_adapter.start()

    def send(self, message, callback) -> None:
        self.inmemory_adapter.send(message, callback)

    def stop(self) -> None:
        self.inmemory_adapter.stop()
        self.rabbitmq_adapter.stop()
        SignalManager.disconnect_all_signals()
