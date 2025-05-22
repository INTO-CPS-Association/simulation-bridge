"""
Infrastructure components for RabbitMQ message routing.
"""
from typing import List, Dict, Any, Optional
import ssl
import pika
from pika.adapters.blocking_connection import BlockingChannel
from ..utils.logger import get_logger

logger = get_logger()


class RabbitMQConnection:
    """Manages RabbitMQ connection and channel creation."""

    def __init__(self,
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
                 retry_delay: int = 5) -> None:
        """
        Initialize a RabbitMQ connection with detailed configuration options.

        Args:
            host: RabbitMQ server hostname or IP address
            port: RabbitMQ server port
            virtual_host: RabbitMQ virtual host
            username: Optional username for authentication
            password: Optional password for authentication
            ssl_enabled: Whether to use SSL/TLS for the connection
            ssl_verify_hostname: Whether to verify hostname in SSL certificates
            ssl_ca_certs: Path to CA certificate file for SSL validation
            ssl_cert_file: Path to client certificate file
            ssl_key_file: Path to client key file
            heartbeat: Heartbeat interval in seconds
            connection_attempts: Number of connection attempts before giving up
            retry_delay: Delay between connection attempts in seconds
        """
        # Prepare connection parameters
        params = {
            'host': host,
            'port': port,
            'virtual_host': virtual_host,
            'heartbeat': heartbeat,
            'connection_attempts': connection_attempts,
            'retry_delay': retry_delay
        }

        # Add credentials only if both username and password are provided
        if username and password:
            params['credentials'] = pika.PlainCredentials(username, password)

        # Add SSL options if enabled
        if ssl_enabled:
            ssl_context = ssl.create_default_context(cafile=ssl_ca_certs)
            ssl_context.check_hostname = ssl_verify_hostname

            if ssl_cert_file and ssl_key_file:
                ssl_context.load_cert_chain(ssl_cert_file, ssl_key_file)

            params['ssl_options'] = pika.SSLOptions(ssl_context)

        self.connection_params = pika.ConnectionParameters(**params)

        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[BlockingChannel] = None

        logger.debug(
            f"RabbitMQ connection configured for {username}@{host}:{port}/{virtual_host}")
        if ssl_enabled:
            logger.debug("SSL/TLS is enabled for RabbitMQ connection")

    def connect(self) -> BlockingChannel:
        """Establish a connection to RabbitMQ and return the channel."""
        try:
            self.connection = pika.BlockingConnection(self.connection_params)
            self.channel = self.connection.channel()
            logger.info("Successfully connected to RabbitMQ server")
            return self.channel
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise

    def close(self) -> None:
        """Close the RabbitMQ connection if it is open."""
        if self.connection and self.connection.is_open:
            logger.debug("Closing RabbitMQ connection")
            self.connection.close()
            logger.debug("RabbitMQ connection closed")


class InfrastructureManager:
    """Manages RabbitMQ infrastructure setup (exchanges, queues, bindings)."""

    def __init__(self, channel: BlockingChannel) -> None:
        """
        Initialize the infrastructure manager.

        Args:
            channel: RabbitMQ channel to use for infrastructure setup
        """
        self.channel: BlockingChannel = channel
        self.logger = get_logger()

    def setup_exchanges(self, exchanges: List[Dict[str, Any]]) -> None:
        """
        Declare exchanges based on the provided configuration.

        Args:
            exchanges: List of exchange configurations
        """
        for exchange in exchanges:
            try:
                self.channel.exchange_declare(
                    exchange=exchange['name'],
                    exchange_type=exchange['type'],
                    durable=exchange.get('durable', True),
                    auto_delete=exchange.get('auto_delete', False),
                    internal=exchange.get('internal', False),
                    arguments=exchange.get('arguments', None)
                )
                self.logger.debug(
                    "Declared exchange: %s (type: %s, durable: %s)",
                    exchange['name'],
                    exchange['type'],
                    exchange.get('durable', True)
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to declare exchange {exchange['name']}: {str(e)}")
                raise

    def setup_queues(self, queues: List[Dict[str, Any]]) -> None:
        """
        Declare queues based on the provided configuration.

        Args:
            queues: List of queue configurations
        """
        for queue in queues:
            try:
                self.channel.queue_declare(
                    queue=queue['name'],
                    durable=queue.get('durable', True),
                    exclusive=queue.get('exclusive', False),
                    auto_delete=queue.get('auto_delete', False),
                    arguments=queue.get('arguments', None)
                )
                self.logger.debug(
                    "Declared queue: %s (durable: %s)",
                    queue['name'],
                    queue.get('durable', True)
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to declare queue {queue['name']}: {str(e)}")
                raise

    def setup_bindings(self, bindings: List[Dict[str, Any]]) -> None:
        """
        Create bindings between queues and exchanges.

        Args:
            bindings: List of binding configurations
        """
        for binding in bindings:
            try:
                self.channel.queue_bind(
                    queue=binding['queue'],
                    exchange=binding['exchange'],
                    routing_key=binding['routing_key'],
                    arguments=binding.get('arguments', None)
                )
                self.logger.debug(
                    "Created binding: %s -> %s (%s)",
                    binding['queue'],
                    binding['exchange'],
                    binding['routing_key']
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to create binding for {binding['queue']} to {binding['exchange']}: {str(e)}")
                raise
