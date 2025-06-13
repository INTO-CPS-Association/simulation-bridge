"""
Signal Manager for the Simulation Bridge.
This module provides a signal management system that handles the registration and
automatic subscription of signals for different protocols in the simulation bridge.
"""
from typing import Callable, Dict, List
from blinker import signal
from .logger import get_logger
from .config_loader import load_protocol_config

logger = get_logger()


class SignalManager:
    """Manages signal registration and automatic subscription for protocols."""

    PROTOCOL_CONFIG = load_protocol_config()
    _bridge_core_instance = None
    _adapter_instances: Dict[str, object] = {}

    @classmethod
    def set_bridge_core(cls, bridge_core_instance):
        """Store the BridgeCore instance for use in signals."""
        cls._bridge_core_instance = bridge_core_instance

    @classmethod
    def register_adapter_instance(cls, protocol: str, adapter_instance: object):
        """Store adapter instances to bind their methods to signals."""
        cls._adapter_instances[protocol] = adapter_instance

    @classmethod
    def get_available_signals(cls, protocol: str) -> List[str]:
        """Return the list of signals available for a given protocol."""
        protocol_data = cls.PROTOCOL_CONFIG.get(protocol)
        return list(protocol_data.get("signals", {}).keys()) if protocol_data else []

    @classmethod
    def connect_all_signals(cls):
        """Auto-connect all signals to the appropriate functions."""
        for protocol, protocol_data in cls.PROTOCOL_CONFIG.items():
            for sig_name, func_path in protocol_data.get("signals", {}).items():
                callback = cls._resolve_callback(func_path, protocol)
                if not callback:
                    logger.warning("Skipping signal '%s': callback not found", sig_name)
                    continue
                try:
                    signal(sig_name).connect(callback)
                    logger.debug("Connected signal '%s' to '%s'", sig_name, func_path)
                except Exception as e: # pylint: disable=broad-exception-caught
                    logger.error("Failed to connect signal '%s': %s", sig_name, e)

    @classmethod
    def _resolve_callback(cls, func_path: str, protocol: str) -> Callable:
        """Resolve a callback function given its string path."""
        if "." not in func_path:
            return None

        class_or_module, func_name = func_path.rsplit(".", 1)

        if class_or_module == "BridgeCore":
            if not cls._bridge_core_instance:
                logger.error("BridgeCore instance not set but required for signal binding")
                return None
            return getattr(cls._bridge_core_instance, func_name, None)

        adapter_instance = cls._adapter_instances.get(protocol)
        if adapter_instance:
            return getattr(adapter_instance, func_name, None)

        logger.warning("No adapter instance registered for protocol '%s'", protocol)
        return None

    @classmethod
    def disconnect_all_signals(cls):
        """Disconnect all signals from their connected callbacks."""
        for protocol, protocol_data in cls.PROTOCOL_CONFIG.items():
            for sig_name, func_path in protocol_data.get("signals", {}).items():
                callback = cls._resolve_callback(func_path, protocol)
                if not callback:
                    logger.warning(
                        "Skipping disconnect of signal '%s': callback not found",
                        sig_name)
                    continue
                try:
                    signal(sig_name).disconnect(callback)
                    logger.debug("Disconnected signal '%s' from '%s'", sig_name,
                                 func_path)
                except Exception as e: # pylint: disable=broad-exception-caught
                    logger.error("Failed to disconnect signal '%s': %s", sig_name,
                                 e)
