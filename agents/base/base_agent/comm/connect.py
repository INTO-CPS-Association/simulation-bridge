"""Shared communication wrapper that abstracts message broker implementations."""

from typing import Any, Callable, Dict, Optional

from .interfaces import IMessageBroker, IMessageHandler

BROKER_NOT_INITIALIZED_ERROR = "Broker not initialized"
BROKER_OR_HANDLER_NOT_INITIALIZED_ERROR = "Broker or message handler not initialized"
BROKER_CONNECTION_FAILED_ERROR = "Failed to connect to broker"


class Connect:
    """Generic communication wrapper for agent message brokers."""

    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-instance-attributes
    def __init__(
        self,
        agent_id: str,
        config: Dict[str, Any],
        broker_type: str,
        broker_factory: Callable[[str, Dict[str, Any]], IMessageBroker],
        message_handler_factory: Callable[[str, IMessageBroker, Dict[str, Any]], IMessageHandler],
        logger: Any,
    ) -> None:
        self.agent_id = agent_id
        self.config = config
        self.broker_type = broker_type
        self.broker_factory = broker_factory
        self.message_handler_factory = message_handler_factory
        self.logger = logger
        self.broker: Optional[IMessageBroker] = None
        self.message_handler: Optional[IMessageHandler] = None
        self._initialize_broker()

    def _initialize_broker(self) -> None:
        """Initialize broker and message handler for the configured broker type."""
        if self.broker_type.lower() != "rabbitmq":
            raise ValueError(f"Unsupported broker type: {self.broker_type}")

        self.logger.info("Initializing RabbitMQ broker")
        self.broker = self.broker_factory(self.agent_id, self.config)
        self.message_handler = self.message_handler_factory(
            self.agent_id, self.broker, self.config)

    def connect(self) -> None:
        """Connect to underlying message broker."""
        if self.broker:
            connected = self.broker.connect()
            if connected is False:
                raise ConnectionError(BROKER_CONNECTION_FAILED_ERROR)
            return
        raise RuntimeError(BROKER_NOT_INITIALIZED_ERROR)

    def setup(self) -> None:
        """Setup exchanges/queues/resources on underlying message broker."""
        if self.broker:
            self.broker.setup_infrastructure()
            return
        raise RuntimeError(BROKER_NOT_INITIALIZED_ERROR)

    def register_message_handler(
            self, custom_handler: Optional[Callable] = None) -> None:
        """Register default or custom callback on the broker."""
        if not self.broker or not self.message_handler:
            raise RuntimeError(BROKER_OR_HANDLER_NOT_INITIALIZED_ERROR)

        if custom_handler:
            self.broker.register_message_handler(custom_handler)
        else:
            self.broker.register_message_handler(
                self.message_handler.handle_message)

    def start_consuming(self) -> None:
        """Start consuming messages, attempting broker connection first."""
        if not self.broker:
            raise RuntimeError(BROKER_NOT_INITIALIZED_ERROR)

        self.logger.debug(
            "Ensuring broker connection is initialized before starting consumption."
        )
        try:
            self.connect()
        except ConnectionError as error:
            self.logger.error(
                "Failed to initialize or reopen broker connection. Consumption aborted: %s",
                error,
            )
            return

        self.logger.debug("Broker connection is active. Starting consumption.")
        self.broker.start_consuming()

    def send_message(self, destination: str, message: Any,
                     **kwargs: Any) -> bool:
        """Send a message to destination via configured broker."""
        if not self.broker:
            raise RuntimeError(BROKER_NOT_INITIALIZED_ERROR)

        if self.broker_type.lower() == "rabbitmq":
            exchange = kwargs.get(
                "exchange",
                self.config.get("exchanges", {}).get("output", "ex.sim.result"),
            )
            default_routing_key = f"{self.agent_id}.{destination}"
            routing_key = kwargs.get("routing_key", default_routing_key)
            properties = kwargs.get("properties", None)
            return self.broker.send_message(
                exchange, routing_key, message, properties)
        return False

    def send_result(self, destination: str, result: Dict[str, Any]) -> bool:
        """Send result payload through broker result channel."""
        if self.broker:
            return self.broker.send_result(destination, result)
        raise RuntimeError(BROKER_NOT_INITIALIZED_ERROR)

    def close(self) -> None:
        """Close broker resources."""
        if self.broker:
            self.broker.close()
        else:
            active_logger = getattr(self, "logger", None)
            if active_logger:
                active_logger.warning(
                    "Attempted to close a non-initialized broker")

    def get_message_handler(self) -> Optional[IMessageHandler]:
        """Return active message handler instance if initialized."""
        return self.message_handler

    def set_simulation_handler(self, handler: Callable) -> None:
        """Inject simulation handler into message handler implementation."""
        if self.message_handler:
            self.message_handler.set_simulation_handler(handler)
