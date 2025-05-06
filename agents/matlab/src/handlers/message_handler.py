"""
Message handler for processing incoming RabbitMQ messages.
"""

import yaml
import uuid
import time
from ..utils.logger import get_logger
from ..batch.batch import handle_batch_simulation
from ..streaming.streaming import handle_streaming_simulation
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
            # logger.debug(f"Message content: {msg}")
            
            # Extract information
            source = method.routing_key.split('.')[0]  # Extract the message source
            sim_type = msg.get('simulation', {}).get('type', 'batch')
            logger.info(f"Received simulation_type: {sim_type}")
            
            # Process the simulation based on type
            if sim_type == 'batch':
                handle_batch_simulation(msg, source, self.rabbitmq_manager)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            elif sim_type == 'streaming':
                # Acknowledge the message before starting streaming
                ch.basic_ack(delivery_tag=method.delivery_tag)
                # Handle streaming simulation
                handle_streaming_simulation(msg, source, self.rabbitmq_manager)
            else:
                logger.error(f"Unknown simulation type: {sim_type}")
            
            # Acknowledge the message after successful processing (ensure streaming completes)
            if sim_type != 'streaming':
                ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except yaml.YAMLError as e:
            logger.error(f"Error decoding YAML message {message_id}: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag)