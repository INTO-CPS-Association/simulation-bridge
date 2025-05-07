"""
MATLAB Agent core implementation.
"""

from typing import Any, Dict
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
    def __init__(self, agent_id: str) -> None:
        """
        Initialize the MATLAB agent with the specified ID.
        
        Args:
            agent_id (str): Unique identifier for this MATLAB agent
        """
        self.agent_id: str = agent_id
        logger.info(f"MATLAB agent ID: {self.agent_id}")
        
        # Load configuration
        self.config_manager: ConfigManager = ConfigManager()
        self.config: Dict[str, Any] = self.config_manager.get_config()
        
        # Setup RabbitMQ manager
        self.rabbitmq_manager: RabbitMQManager = RabbitMQManager(self.agent_id, self.config)
        
        # Setup message handler
        self.message_handler: MessageHandler = MessageHandler(self.agent_id, self.rabbitmq_manager)
        
        # Register message handler with RabbitMQ manager
        self.rabbitmq_manager.register_message_handler(self.message_handler.handle_message)
    
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
        except Exception as e:
            logger.error(f"Error while consuming messages: {e}")
            self.stop()
    
    def stop(self) -> None:
        """
        Stop the agent and close connections.
        """
        logger.info("Stopping MATLAB agent")
        self.rabbitmq_manager.close()