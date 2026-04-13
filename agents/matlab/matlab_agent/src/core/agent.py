"""
MatlabAgent implementation - An implementation of the MatlabAgent class using the Connect
abstraction to manage communication and handle simulation processing.
"""

from typing import Any, Dict, Optional

import pika
import yaml
from base_agent.comm.connect import Connect
from base_agent.comm.rabbitmq.rabbitmq_manager import RabbitMQManager
from base_agent.interfaces.config_manager import IConfigManager
from base_agent.utils.logger import get_logger

from ..comm.rabbitmq.message_handler import MessageHandler
from ..utils.config_manager import ConfigManager
from ..utils.performance_monitor import PerformanceMonitor

# Configure logger
logger = get_logger("MATLAB-AGENT")


class MatlabAgent:
    """
    An agent that interfaces with a MATLAB simulation through a communication layer.
    This component handles message reception, processing, and result distribution
    while remaining decoupled from the specific messaging technology.
    """

    def __init__(
            self,
            agent_id: str,
            config_path: Optional[str] = None,
            broker_type: str = "rabbitmq") -> None:
        """
        Initialize the MATLAB agent.

        Args:
            agent_id (str): The ID of the agent
            config_path (Optional[str]): Path to the configuration file (optional)
            broker_type (str): The type of message broker to use (default: "rabbitmq")
        """
        self.agent_id: str = agent_id
        logger.info("Initializing MATLAB agent with ID: %s", self.agent_id)

        # Load configuration
        self.config_manager: IConfigManager = ConfigManager(config_path)
        self.config: Dict[str, Any] = self.config_manager.get_config()

        # Initialize performance monitor
        self.performance_monitor = PerformanceMonitor(config=self.config)

        def broker_factory(
            current_agent_id: str,
            current_config: Dict[str, Any],
        ) -> RabbitMQManager:
            return RabbitMQManager(
                agent_id=current_agent_id,
                config=current_config,
                logger=logger,
                pika_module=pika,
                yaml_module=yaml,
            )

        # Initialize the communication layer
        self.comm = Connect(
            agent_id=self.agent_id,
            config=self.config,
            broker_type=broker_type,
            broker_factory=broker_factory,
            message_handler_factory=MessageHandler,
            logger=logger,
        )
        # Set up the communication infrastructure
        self.comm.connect()
        self.comm.setup()
        self.comm.register_message_handler()
        logger.debug("MATLAB agent initialized successfully")

    def start(self) -> None:
        """
        Start the agent and begin consuming messages.
        """
        try:
            logger.info("MATLAB agent running and listening for requests")
            self.comm.start_consuming()
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
        except Exception as e:
            # For all other unexpected errors
            logger.error("Unexpected error while consuming messages: %s", e)
            # This will log the full stack trace
            logger.exception("Stack trace:")
            self.stop()

    def stop(self) -> None:
        """
        Stop the agent and close all connections.
        """
        logger.info("Stopping MATLAB agent")
        self.comm.close()

        # Log performance summary before stopping
        summary = self.performance_monitor.get_summary()
        if summary:
            logger.info("Performance Summary:")
            for metric, value in summary.items():
                logger.info("  %s: %.2f", metric, value)

    def send_result(self, destination: str, result: Dict[str, Any]) -> bool:
        """
        Send operation results to the specified destination.

        Args:
            destination (str): The destination identifier
            result (Dict[str, Any]): The result data to be sent

        Returns:
            bool: True if successful, False otherwise
        """
        success = self.comm.send_result(destination, result)
        if success:
            self.performance_monitor.record_result_sent()
        return success
