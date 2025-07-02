from typing import Dict, Any, Callable

from blinker import signal

from ...utils.config_manager import ConfigManager
from ...utils.logger import get_logger
from ..base.protocol_adapter import ProtocolAdapter

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

        # registra il callback
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
            # nessun callback *ancora* registrato ⇒ accoda
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
