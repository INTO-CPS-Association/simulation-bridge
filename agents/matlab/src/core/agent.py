"""
MATLAB Agent core implementation.
"""

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
    def __init__(self, agent_id):
        """
        Initialize the MATLAB agent with the specified ID.
        
        Args:
            agent_id (str): Unique identifier for this MATLAB agent
        """
        self.agent_id = agent_id
        logger.info(f"Initializing MATLAB agent with ID: {self.agent_id}")
        
        # Load configuration
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()
        
        # Setup RabbitMQ manager
        self.rabbitmq_manager = RabbitMQManager(self.agent_id, self.config)
        
        # Setup message handler
        self.message_handler = MessageHandler(self.agent_id, self.rabbitmq_manager)
        
        # Register message handler with RabbitMQ manager
        self.rabbitmq_manager.register_message_handler(self.message_handler.handle_message)
    
    def start(self):
        """
        Start consuming messages from the input queue.
        """
        try:
            logger.info(f"MATLAB agent {self.agent_id} started. Listening for simulation requests...")
            self.rabbitmq_manager.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping MATLAB agent due to keyboard interrupt")
            self.stop()
        except Exception as e:
            logger.error(f"Error while consuming messages: {e}")
            self.stop()
    
    def stop(self):
        """
        Stop the agent and close connections.
        """
        logger.info("Stopping MATLAB agent")
        self.rabbitmq_manager.close()