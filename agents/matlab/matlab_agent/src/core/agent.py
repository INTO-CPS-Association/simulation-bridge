"""
MATLAB Agent core implementation.
"""
from typing import Any, Dict, Optional
import pika
from ..interfaces.config_manager import IConfigManager
from ..interfaces.rabbitmq_manager import IRabbitMQManager
from ..interfaces.message_handler import IMessageHandler
from .config_manager import ConfigManager
from .rabbitmq_manager import RabbitMQManager
from ..handlers.message_handler import MessageHandler
from ..utils.logger import get_logger

logger = get_logger()


class MatlabAgent:
    """
    An agent that interfaces with a MATLAB simulation via RabbitMQ.
    This component handles message reception, processing, and result distribution.
    """

    def __init__(self, agent_id: str, config_path: Optional[str] = None) -> None:
        """
        Initialize the MATLAB agent with the specified ID, and optionally a configuration file.
        """
        self.agent_id: str = agent_id
        logger.info("MATLAB agent ID: %s", self.agent_id)

        # Load configuration
        self.config_manager: IConfigManager = ConfigManager(config_path)
        self.config: Dict[str, Any] = self.config_manager.get_config()

        # Setup RabbitMQ manager
        self.rabbitmq_manager: IRabbitMQManager = RabbitMQManager(
            self.agent_id, self.config)

        # Setup message handler
        self.message_handler: IMessageHandler = MessageHandler(
            self.agent_id, self.rabbitmq_manager)

        # Register message handler with RabbitMQ manager
        self.rabbitmq_manager.register_message_handler(
            self.message_handler.handle_message)

    def start(self) -> None:
        """
        Start consuming messages from the input queue.
        """
        try:
            logger.info("MATLAB agent running and listening for requests")
            self.rabbitmq_manager.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping MATLAB agent due to keyboard interrupt")
            self.stop()
        except ConnectionError as e:
            # Specific handling for ConnectionError
            logger.error("Connection error while consuming messages: %s", e)
            self.stop()
        except TimeoutError as e:
            # Specific handling for TimeoutError
            logger.error("Timeout error while consuming messages: %s", e)
            self.stop()
        except (pika.exceptions.AMQPError,
                pika.exceptions.ChannelError,
                pika.exceptions.ConnectionClosedByBroker) as e:
            # More specific RabbitMQ-related exceptions
            logger.error("RabbitMQ error while consuming messages: %s", e)
            self.stop()
        except Exception as e:
            # Only for truly unexpected errors not covered by specific cases
            logger.error("Unexpected error while consuming messages: %s", e)
            # This will log the full stack trace
            logger.exception("Stack trace:")
            self.stop()

    def stop(self) -> None:
        """
        Stop the agent and close connections.
        """
        logger.info("Stopping MATLAB agent")
        self.rabbitmq_manager.close()
