"""
AnylogicAgent implementation - An implementation of the AnylogicAgent class using the Connect
abstraction to manage communication and handle simulation processing.
"""

from typing import Any, Dict, Optional
import threading

from .listener import Listener

from ..interfaces.config_manager import IConfigManager
from ..utils.config_manager import ConfigManager
from ..utils.logger import get_logger
from ..comm.connect import Connect

# Configure logger
logger = get_logger()


class AnylogicAgent:
    """
    An agent that interfaces with a Anylogic simulation through a communication layer.
    This component handles message reception, processing, and result distribution
    while remaining decoupled from the specific messaging technology.
    """

    def __init__(
            self,
            agent_id: str,
            config_path: Optional[str] = None,
            broker_type: str = "rabbitmq") -> None:
        """
        Initialize the ANYLOGIC Agent.

        Args:
            agent_id (str): The ID of the agent
            config_path (Optional[str]): Path to the configuration file (optional)
            broker_type (str): The type of message broker to use (default: "rabbitmq")
        """
        self.agent_id: str = agent_id
        logger.info("Initializing ANYLOGIC Agent with ID: %s", self.agent_id)

        # Load configuration
        self.config_manager: IConfigManager = ConfigManager(config_path)
        self.config: Dict[str, Any] = self.config_manager.get_config()
        # Initialize the communication layer
        self.comm = Connect(self.agent_id, self.config, broker_type)
        # Set up the communication infrastructure
        self.comm.connect()
        self.comm.setup()
        self.comm.register_message_handler()
        # Initialize UDP Listener
        self.listener = Listener(self.config)
        logger.debug("ANYLOGIC Agent initialized successfully")

    def start(self) -> None:
        """
        Start the agent and begin consuming messages.
        """
        try:
            logger.info("Starting UDP Listener")
            listener_thread = threading.Thread(
                target=self.listener.start,
                name="udp-listener",
                daemon=True,
            )
            listener_thread.start()

            logger.info("ANYLOGIC Agent running and listening for requests")
            # Block in RabbitMQ consumption on the main thread
            self.comm.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping ANYLOGIC Agent due to keyboard interrupt")
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
        logger.info("Stopping ANYLOGIC Agent")
        # Stop UDP listener first
        try:
            self.listener.stop()
        except Exception:  # Listener may already be stopped
            pass
        self.comm.close()

        # Performance monitor may not be present; guard usage
        perf = getattr(self, "performance_monitor", None)
        if perf:
            summary = perf.get_summary()
            if summary:
                logger.info("Performance Summary:")
                for metric, value in summary.items():
                    logger.info(f"  {metric}: {value:.2f}")

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
        perf = getattr(self, "performance_monitor", None)
        if success and perf:
            perf.record_result_sent()
        return success
