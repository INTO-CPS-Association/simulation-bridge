"""
Signal Manager for the Simulation Bridge.
This module provides a signal management system that handles the registration and
automatic subscription of signals for different protocols in the simulation bridge.
"""
from typing import Callable, Dict, List, Optional
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
    def register_adapter_instance(
            cls, protocol: str, adapter_instance: object):
        """Store adapter instances to bind their methods to signals."""
        cls._adapter_instances[protocol] = adapter_instance

    @classmethod
    def get_available_signals(cls, protocol: str) -> List[str]:
        """Return the list of signals available for a given protocol."""
        protocol_data = cls.PROTOCOL_CONFIG.get(protocol)
        return list(protocol_data.get("signals", {}).keys()
                    ) if protocol_data else []

    @classmethod
    def get_enabled_protocols(cls) -> List[str]:
        """Return the list of enabled protocols."""
        enabled_protocols = []
        for protocol, protocol_data in cls.PROTOCOL_CONFIG.items():
            if protocol_data.get(
                    "enabled", True):  # Default to True for backward compatibility
                enabled_protocols.append(protocol)
        return enabled_protocols

    @classmethod
    def is_protocol_enabled(cls, protocol: str) -> bool:
        """Check if a protocol is enabled."""
        protocol_data = cls.PROTOCOL_CONFIG.get(protocol)
        if not protocol_data:
            return False
        # Default to True for backward compatibility
        return protocol_data.get("enabled", True)

    @classmethod
    def connect_all_signals(cls):
        """Auto-connect all signals to the appropriate functions for enabled protocols only."""
        for protocol, protocol_data in cls.PROTOCOL_CONFIG.items():
            # Skip disabled protocols
            if not protocol_data.get("enabled", True):
                logger.debug(
                    "Skipping signals for disabled protocol: %s",
                    protocol)
                continue

            for sig_name, func_path in protocol_data.get(
                    "signals", {}).items():
                callback = cls._resolve_callback(func_path, protocol)
                if not callback:
                    logger.warning(
                        "Skipping signal '%s': callback not found", sig_name)
                    continue
                try:
                    signal(sig_name).connect(callback)
                    logger.debug(
                        "Connected signal '%s' to '%s' for protocol '%s'",
                        sig_name,
                        func_path,
                        protocol)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error(
                        "Failed to connect signal '%s': %s", sig_name, e)

    @classmethod
    def connect_inmemory_signals(cls):
        """Connect only signals related to the 'inmemory' protocol."""
        protocol = "inmemory"
        protocol_data = cls.PROTOCOL_CONFIG.get(protocol)

        if not protocol_data or not protocol_data.get("enabled", True):
            logger.debug(
                "Skipping signals for disabled or missing 'inmemory' protocol.")
            return

        for sig_name, func_path in protocol_data.get("signals", {}).items():
            callback = cls._resolve_callback(
                func_path, protocol, strict_protocol="inmemory")
            if not callback:
                logger.warning(
                    "Skipping signal '%s': callback not found", sig_name)
                continue
            try:
                signal(sig_name).connect(callback)
                logger.debug("Connected signal '%s' to '%s' for protocol 'inmemory'",
                             sig_name, func_path)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to connect signal '%s': %s", sig_name, e)

    @classmethod
    def _resolve_callback(cls, func_path: str, protocol: str,
                          strict_protocol: Optional[str] = None) -> Callable:
        """Resolve a callback function given its string path."""
        if strict_protocol and protocol != strict_protocol:
            logger.debug(
                "Skipping callback resolution: protocol '%s' != strict '%s'",
                protocol,
                strict_protocol)
            return None

        if "." not in func_path:
            return None

        class_or_module, func_name = func_path.rsplit(".", 1)

        if class_or_module == "BridgeCore":
            if not cls._bridge_core_instance:
                logger.error(
                    "BridgeCore instance not set but required for signal binding")
                return None
            return getattr(cls._bridge_core_instance, func_name, None)

        adapter_instance = cls._adapter_instances.get(protocol)
        if adapter_instance:
            return getattr(adapter_instance, func_name, None)

        logger.warning(
            "No adapter instance registered for protocol '%s'",
            protocol)
        return None

    @classmethod
    def disconnect_all_signals(cls):
        """Disconnect all signals from their connected callbacks for enabled protocols only."""
        for protocol, protocol_data in cls.PROTOCOL_CONFIG.items():
            # Skip disabled protocols (they shouldn't have connected signals
            # anyway)
            if not protocol_data.get("enabled", True):
                logger.debug(
                    "Skipping signal disconnection for disabled protocol: %s",
                    protocol)
                continue

            for sig_name, func_path in protocol_data.get(
                    "signals", {}).items():
                callback = cls._resolve_callback(func_path, protocol)
                if not callback:
                    logger.warning(
                        "Skipping disconnect of signal '%s': callback not found",
                        sig_name)
                    continue
                try:
                    signal(sig_name).disconnect(callback)
                    logger.debug("Disconnected signal '%s' from '%s' for protocol '%s'",
                                 sig_name, func_path, protocol)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error("Failed to disconnect signal '%s': %s", sig_name,
                                 e)
