"""
Bridge Orchestrator for managing Digital Twins (DTs), Physical Twins (PTs) or
Mock Physical Twins (MockPTs) and simulators counterparts communication via RabbitMQ.
"""
from typing import Any, Dict, Optional
from pika.adapters.blocking_connection import BlockingChannel

from .infrastructure import RabbitMQConnection, InfrastructureManager
from .config_manager import ConfigManager
from ..interfaces.config_manager import IConfigManager
from ..interfaces.infrastructure import IInfrastructureManager, IRabbitMQConnection
from ..utils.logger import get_logger
from ..handlers.rabbitmq.rabbitmq_simulation_input_handler import SimulationInputMessageHandler
from ..handlers.rabbitmq.rabbitmq_simulation_result_handler import SimulationResultMessageHandler

logger = get_logger()


class BridgeOrchestrator:
    """
    Bridge Orchestrator class that manages the communication between
    Digital Twins (DTs) or Mock Physical Twins (MockPTs) and simulators
    """

    def __init__(self,
                 simulation_bridge_id: str,
                 config_path: Optional[str] = None) -> None:
        """
        Initialize the Bridge Orchestrator with the specified configuration file.

        Args:
            simulation_bridge_id: Unique identifier for this bridge instance
            config_path: Optional path to the configuration file
        """
        self.simulation_bridge_id: str = simulation_bridge_id
        logger.info(
            "Initializing Simulation Bridge with ID: %s",
            self.simulation_bridge_id)

        # Load configuration
        self.config_manager: IConfigManager = ConfigManager(config_path)
        self.config: Dict[str, Any] = self.config_manager.get_config()
        self.rmq_config: Dict[str,
                              Any] = self.config_manager.get_rabbitmq_config()

        # Setup RabbitMQ connection with enhanced configuration
        logger.debug("Initializing RabbitMQ connection")
        self.conn: IRabbitMQConnection = self._create_rabbitmq_connection()
        self.channel: BlockingChannel = self.conn.connect()

        # Initialize message handlers
        self.input_handler: SimulationInputMessageHandler = SimulationInputMessageHandler(
            self.channel)
        self.result_handler: SimulationResultMessageHandler = SimulationResultMessageHandler(
            self.channel)

        self.setup_infrastructure()

    def _create_rabbitmq_connection(self) -> IRabbitMQConnection:
        """
        Create a RabbitMQ connection with parameters from config.

        Returns:
            Configured RabbitMQ connection
        """
        rmq_config = self.rmq_config

        # Extract all connection parameters from config with defaults
        connection_params = {
            'host': rmq_config.get('host', 'localhost'),
            'port': rmq_config.get('port', 5672),
            'virtual_host': rmq_config.get('virtual_host', '/')
        }

        # Only add username and password if both are provided
        username = rmq_config.get('username')
        password = rmq_config.get('password')
        if username and password:
            connection_params['username'] = username
            connection_params['password'] = password

        # Add connection reliability parameters
        connection_params.update({
            'heartbeat': rmq_config.get('heartbeat', 600),
            'connection_attempts': rmq_config.get('connection_attempts', 3),
            'retry_delay': rmq_config.get('retry_delay', 5)
        })

        # SSL/TLS configuration if enabled
        ssl_config = rmq_config.get('ssl', {})
        if ssl_config.get('enabled', False):
            connection_params.update({
                'ssl_enabled': True,
                'ssl_verify_hostname': ssl_config.get('verify_hostname', True),
                'ssl_ca_certs': ssl_config.get('ca_certs'),
                'ssl_cert_file': ssl_config.get('cert_file'),
                'ssl_key_file': ssl_config.get('key_file')
            })

        return RabbitMQConnection(**connection_params)

    def setup_infrastructure(self) -> None:
        """Set up RabbitMQ infrastructure based on configuration."""
        logger.debug("Configuring RabbitMQ infrastructure")
        infra_config: Dict[str,
                           Any] = self.config_manager.get_infrastructure_config()

        # Configuring exchanges
        try:
            logger.debug("Configuring exchanges...")
            im: IInfrastructureManager = InfrastructureManager(self.channel)
            im.setup_exchanges(infra_config.get('exchanges', []))
            logger.debug("Exchanges configured successfully")
        except Exception as e:
            logger.error(f"Error during exchange configuration: {str(e)}")
            raise  # Re-raise the exception to stop the process in case of error

        # Configuring queues
        try:
            logger.debug("Configuring queues...")
            im.setup_queues(infra_config.get('queues', []))
            logger.debug("Queues configured successfully")
        except Exception as e:
            logger.error(f"Error during queue configuration: {str(e)}")
            raise  # Re-raise the exception to stop the process in case of error

        # Configuring bindings
        try:
            logger.debug("Configuring bindings...")
            im.setup_bindings(infra_config.get('bindings', []))
            logger.debug("Bindings configured successfully")
        except Exception as e:
            logger.error(f"Error during binding configuration: {str(e)}")
            raise  # Re-raise the exception to stop the process in case of error

        logger.info("RabbitMQ infrastructure configured successfully")

    def start(self) -> None:
        """Start the bridge orchestrator and begin processing messages."""
        prefetch_count = self.rmq_config.get('prefetch_count', 1)
        self.channel.basic_qos(prefetch_count=prefetch_count)
        logger.debug(f"Set QoS prefetch count to {prefetch_count}")

        # Consume input messages (from DTs to simulators)
        self.channel.basic_consume(
            queue='Q.bridge.input',
            on_message_callback=self.input_handler.handle
        )
        logger.debug("Started consuming from Q.bridge.input")

        # Consume result messages (from simulators to DTs)
        self.channel.basic_consume(
            queue='Q.bridge.result',
            on_message_callback=self.result_handler.handle
        )
        logger.debug("Started consuming from Q.bridge.result")

        logger.info("Bridge Orchestrator running - waiting for messages")
        self.channel.start_consuming()

    def stop(self) -> None:
        """Stop the bridge orchestrator and close connections."""
        if self.channel and self.channel.is_open:
            logger.debug("Stopping message consumption")
            self.channel.stop_consuming()

        if self.conn:
            logger.debug("Closing RabbitMQ connection")
            self.conn.close()

        logger.info("Bridge Orchestrator stopped")
