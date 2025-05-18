"""
Generic communication wrapper that abstracts underlying messaging protocols.
This module provides a unified interface for communication, regardless of the
underlying technology (RabbitMQ, Kafka, etc.) being used.
"""
from typing import Any, Dict, Optional, Callable

from ..utils.logger import get_logger
from .interfaces import IMessageBroker, IMessageHandler
from .rabbitmq.rabbitmq_manager import RabbitMQManager
from .rabbitmq.message_handler import MessageHandler

logger = get_logger()


class Connect:
    """
    A communication wrapper that provides a unified interface for messaging,
    abstracting the underlying messaging protocol implementation.
    """

    def __init__(
            self,
            agent_id: str,
            config: Dict[str, Any],
            broker_type: str = "rabbitmq") -> None:
        """
        Initialize the communication wrapper.

        Args:
            agent_id (str): The ID of the agent
            config (Dict[str, Any]): Configuration parameters
            broker_type (str): The type of message broker to use (default: "rabbitmq")
        """
        self.agent_id = agent_id
        self.config = config
        self.broker_type = broker_type
        self.broker: Optional[IMessageBroker] = None
        self.message_handler: Optional[IMessageHandler] = None

        # Initialize the appropriate message broker based on the type
        self._initialize_broker()

    def _initialize_broker(self) -> None:
        """
        Initialize the appropriate message broker based on the type.
        """
        if self.broker_type.lower() == "rabbitmq":
            logger.info("Initializing RabbitMQ broker")
            self.broker = RabbitMQManager(self.agent_id, self.config)
            path_simulation = self.config.get(
                'simulation', {}).get(
                'path', None)
            self.message_handler = MessageHandler(
                self.agent_id, self.broker, path_simulation)
        else:
            raise ValueError(f"Unsupported broker type: {self.broker_type}")

    def connect(self) -> None:
        """
        Establish a connection to the message broker.
        """
        if self.broker:
            self.broker.connect()
        else:
            raise RuntimeError("Broker not initialized")

    def setup(self) -> None:
        """
        Set up the required infrastructure for the messaging system.
        """
        if self.broker:
            self.broker.setup_infrastructure()
        else:
            raise RuntimeError("Broker not initialized")

    def register_message_handler(
            self, custom_handler: Optional[Callable] = None) -> None:
        """
        Register a function to handle incoming messages.

        Args:
            custom_handler (Optional[Callable]): A custom handler function
            to use instead of the default. If None, the default handler will
            be used
        """
        if self.broker and self.message_handler:
            if custom_handler:
                self.broker.register_message_handler(custom_handler)
            else:
                self.broker.register_message_handler(
                    self.message_handler.handle_message)
        else:
            raise RuntimeError("Broker or message handler not initialized")

    def start_consuming(self) -> None:
        """
        Start consuming messages from the input channel.
        """
        if not self.broker:
            raise RuntimeError("Broker not initialized")

        if not self.broker.channel or not self.broker.channel.is_open:
            logger.debug(
                "Channel is not initialized or is closed. Attempting to reconnect...")
            if not self.broker.connect():
                logger.error(
                    "Failed to initialize or reopen channel. Consumption aborted.")
                return

        logger.debug("Channel is active. Starting consumption.")
        self.broker.start_consuming()

    def send_message(
            self,
            destination: str,
            message: Any,
            **kwargs) -> bool:
        """
        Send a message to a specified destination.

        Args:
            destination (str): The destination identifier
            message (Any): The message to send
            **kwargs: Additional parameters specific to the implementation

        Returns:
            bool: True if successful, False otherwise
        """
        if self.broker:
            # For RabbitMQ, we need to extract specific parameters
            if self.broker_type.lower() == "rabbitmq":
                exchange = kwargs.get(
                    "exchange", self.config.get(
                        "exchanges", {}).get(
                        "output", "ex.sim.result"))
                routing_key = kwargs.get(
                    "routing_key", f"{self.agent_id}.{destination}")
                properties = kwargs.get("properties", None)
                return self.broker.send_message(
                    exchange, routing_key, message, properties)
            # Handle other broker types here in the future
            return False
        else:
            raise RuntimeError("Broker not initialized")

    def send_result(self, destination: str, result: Dict[str, Any]) -> bool:
        """
        Send operation results to the specified destination.

        Args:
            destination (str): The destination identifier
            result (Dict[str, Any]): The result data to be sent

        Returns:
            bool: True if successful, False otherwise
        """
        if self.broker:
            return self.broker.send_result(destination, result)
        else:
            raise RuntimeError("Broker not initialized")

    def close(self) -> None:
        """
        Close the connection to the message broker.
        """
        if self.broker:
            self.broker.close()
        else:
            logger.warning("Attempted to close a non-initialized broker")

    def get_message_handler(self) -> Optional[IMessageHandler]:
        """
        Get the current message handler.

        Returns:
            Optional[IMessageHandler]: The current message handler or None if not initialized
        """
        return self.message_handler

    def set_simulation_handler(self, handler: Callable) -> None:
        """
        Set the handler for simulation messages.
        This provides a way to inject the simulation handler without creating
        circular dependencies.

        Args:
            handler (Callable): The function to handle simulation messages
        """
        if self.message_handler:
            self.message_handler.set_simulation_handler(handler)
