from typing import Optional, List, Dict, Any
from pika.adapters.blocking_connection import BlockingChannel


class IRabbitMQConnection:
    """
    Interface for managing RabbitMQ connection and channel creation.
    """

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 5672,
        virtual_host: str = '/',
        username: Optional[str] = None,
        password: Optional[str] = None,
        ssl_enabled: bool = False,
        ssl_verify_hostname: bool = True,
        ssl_ca_certs: Optional[str] = None,
        ssl_cert_file: Optional[str] = None,
        ssl_key_file: Optional[str] = None,
        heartbeat: int = 600,
        connection_attempts: int = 3,
        retry_delay: int = 5
    ) -> None:
        """
        Initialize RabbitMQ connection parameters.
        """

    def connect(self) -> BlockingChannel:
        """
        Establish and return a RabbitMQ channel.

        Returns:
            BlockingChannel: RabbitMQ channel object.

        Raises:
            Exception: On connection failure.
        """

    def close(self) -> None:
        """
        Close the RabbitMQ connection if open.
        """


class IInfrastructureManager:
    """
    Interface for managing RabbitMQ infrastructure: exchanges, queues, bindings.
    """

    def __init__(self, channel: BlockingChannel) -> None:
        """
        Initialize with a RabbitMQ channel.

        Args:
            channel (BlockingChannel): RabbitMQ channel for infrastructure setup.
        """

    def setup_exchanges(self, exchanges: List[Dict[str, Any]]) -> None:
        """
        Declare RabbitMQ exchanges.

        Args:
            exchanges (List[Dict[str, Any]]): Exchange configurations.

        Raises:
            Exception: On failure to declare an exchange.
        """

    def setup_queues(self, queues: List[Dict[str, Any]]) -> None:
        """
        Declare RabbitMQ queues.

        Args:
            queues (List[Dict[str, Any]]): Queue configurations.

        Raises:
            Exception: On failure to declare a queue.
        """

    def setup_bindings(self, bindings: List[Dict[str, Any]]) -> None:
        """
        Create bindings between queues and exchanges.

        Args:
            bindings (List[Dict[str, Any]]): Binding configurations.

        Raises:
            Exception: On failure to create a binding.
        """
