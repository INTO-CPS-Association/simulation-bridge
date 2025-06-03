"""Signal management module for protocol-specific signal handling."""

from typing import List
from blinker import signal
from .logger import get_logger

logger = get_logger()


class SignalManager:
    """Manages signal registration and subscription for different protocols."""

    # Define available signals for each protocol
    PROTOCOL_SIGNALS = {
        'rabbitmq': [
            'message_received_input_rabbitmq',
            'message_received_result_rabbitmq',
            'message_received_other_rabbitmq'
        ],
        'mqtt': [
            'message_received_input_mqtt'
        ],
        'rest': [
            'message_received_input_rest'
        ]
    }

    @classmethod
    def get_available_signals(cls, protocol: str) -> List[str]:
        """Get list of available signals for a specific protocol.

        Args:
            protocol: Protocol name (rabbitmq, mqtt, rest)

        Returns:
            List of available signal names for the protocol
        """
        return cls.PROTOCOL_SIGNALS.get(protocol, [])

    @classmethod
    def connect_signal(cls, protocol: str, signal_name: str, callback) -> bool:
        """Connect a callback to a signal if allowed for the protocol.

        Args:
            protocol: Protocol name (rabbitmq, mqtt, rest)
            signal_name: Name of the signal to connect to
            callback: Callback function to connect

        Returns:
            bool: True if connection was successful, False otherwise
        """
        if signal_name not in cls.get_available_signals(protocol):
            logger.warning(
                "Attempted to connect to unauthorized signal '%s' "
                "for protocol '%s'", signal_name, protocol
            )
            return False

        try:
            signal(signal_name).connect(callback)
            logger.debug(
                "Connected signal '%s' for protocol '%s'", signal_name, protocol
            )
            return True
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error connecting to signal '%s' for protocol '%s': %s",
                signal_name, protocol, exc
            )
            return False

    @classmethod
    def disconnect_signal(cls, protocol: str,
                          signal_name: str, callback) -> bool:
        """Disconnect a callback from a signal if allowed for the protocol.

        Args:
            protocol: Protocol name (rabbitmq, mqtt, rest)
            signal_name: Name of the signal to disconnect from
            callback: Callback function to disconnect

        Returns:
            bool: True if disconnection was successful, False otherwise
        """
        if signal_name not in cls.get_available_signals(protocol):
            logger.warning(
                "Attempted to disconnect from unauthorized signal '%s' "
                "for protocol '%s'", signal_name, protocol
            )
            return False

        try:
            signal(signal_name).disconnect(callback)
            logger.debug(
                "Disconnected signal '%s' for protocol '%s'", signal_name, protocol
            )
            return True
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error disconnecting from signal '%s' for protocol '%s': %s",
                signal_name, protocol, exc
            )
            return False
