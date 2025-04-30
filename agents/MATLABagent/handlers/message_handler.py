"""
Message handler for processing incoming RabbitMQ messages.
"""

import yaml
import uuid
import time
from ..utils.logger import get_logger
logger = get_logger()


class MessageHandler:
    """
    Handler for processing incoming messages from RabbitMQ.
    """
    def __init__(self, agent_id, rabbitmq_manager):
        """
        Initialize the message handler.
        
        Args:
            agent_id (str): The ID of the agent
            rabbitmq_manager (RabbitMQManager): The RabbitMQ manager instance
        """
        self.agent_id = agent_id
        self.rabbitmq_manager = rabbitmq_manager
    
    def handle_message(self, ch, method, properties, body):
        """
        Process incoming messages from RabbitMQ.
        
        Args:
            ch: Channel object
            method: Delivery method
            properties: Message properties
            body: Message body
        """
        message_id = properties.message_id if properties.message_id else "unknown"
        logger.info(f"Received message {message_id}")
        logger.debug(f"Message routing key: {method.routing_key}")
        
        try:
            # Load the message body as YAML
            msg = yaml.safe_load(body)
            logger.debug(f"Message content: {msg}")
            
            # Extract information
            source = method.routing_key.split('.')[0]  # Extract the message source
            sim_type = msg.get('simulation', {}).get('type', 'batch')
            
            logger.info(f"Processing {sim_type} simulation request from {source}")
            
            # Process the message and get result
            result = self.process_message(sim_type, msg)
            
            # Send the result back
            self.rabbitmq_manager.send_result(source, result)
            
            # Acknowledge the receipt of the original message
            ch.basic_ack(method.delivery_tag)
            logger.info(f"Successfully processed message {message_id}")
            
        except yaml.YAMLError as e:
            logger.error(f"Error decoding YAML message {message_id}: {e}")
            ch.basic_nack(method.delivery_tag)
        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}")
            ch.basic_nack(method.delivery_tag)
    
    def process_message(self, sim_type, msg):
        """
        Process a message and generate a result.
        
        Args:
            sim_type (str): The type of simulation
            msg (dict): The message content
            
        Returns:
            dict: The result of processing the message
        """
        # For now, create a dummy result
        # In the future, this method could be expanded to include actual simulation logic
        # or call to external MATLAB processes
        
        result = {
            'simulation_id': str(uuid.uuid4()),
            'sim_type': sim_type,
            'timestamp': time.time(),
            'status': 'processed_by_agent',
            'message': 'This is a placeholder. Real simulation will be implemented later.'
        }
        
        return result