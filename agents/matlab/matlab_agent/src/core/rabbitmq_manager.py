"""
RabbitMQ connection and infrastructure management for the MATLAB Agent.
"""

import pika
import yaml
import uuid
import sys
from typing import Dict, Callable, Optional, Any
from pika.spec import BasicProperties
from ..utils.logger import get_logger

logger = get_logger()


class RabbitMQManager:
    """
    Manager for RabbitMQ connections, channels, exchanges, and queues.
    """
    def __init__(self, agent_id: str, config: Dict[str, Any]) -> None:
        """
        Initialize the RabbitMQ manager.
        
        Args:
            agent_id (str): The ID of the agent
            config (dict): Configuration parameters
        """
        self.agent_id: str = agent_id
        self.config: Dict[str, Any] = config
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        self.input_queue_name: str = f'Q.sim.{self.agent_id}'
        self.message_handler: Optional[Callable[[pika.adapters.blocking_connection.BlockingChannel, pika.spec.Basic.Deliver, BasicProperties, bytes], None]] = None
        
        # Connect to RabbitMQ
        self.connect()
        # Setup exchanges and queues
        self.setup_infrastructure()
    
    def connect(self) -> None:
        """
        Establish connection to RabbitMQ server using configuration parameters.
        """
        rabbitmq_config: Dict[str, Any] = self.config.get('rabbitmq', {})
        try:
            logger.debug(f"Connecting to RabbitMQ at {rabbitmq_config.get('host', 'localhost')}...")
            
            # Setup connection parameters
            credentials = pika.PlainCredentials(
                rabbitmq_config.get('username', 'guest'),
                rabbitmq_config.get('password', 'guest')
            )
            
            parameters = pika.ConnectionParameters(
                host=rabbitmq_config.get('host', 'localhost'),
                port=rabbitmq_config.get('port', 5672),
                credentials=credentials,
                heartbeat=rabbitmq_config.get('heartbeat', 600)
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info("Successfully connected to RabbitMQ")
            
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            sys.exit(1)
    
    def setup_infrastructure(self) -> None:
        """
        Set up the RabbitMQ infrastructure (exchanges, queues, bindings).
        """
        exchanges: Dict[str, str] = self.config.get('exchanges', {})
        queue_config: Dict[str, Any] = self.config.get('queue', {})
        
        try:
            # Input exchange to receive commands
            input_exchange: str = exchanges.get('input', 'ex.bridge.output')
            self.channel.exchange_declare(
                exchange=input_exchange,
                exchange_type='topic',
                durable=True
            )
            logger.debug(f"Declared input exchange: {input_exchange}")
            
            # Output exchange to send results
            output_exchange: str = exchanges.get('output', 'ex.sim.result')
            self.channel.exchange_declare(
                exchange=output_exchange,
                exchange_type='topic',
                durable=True
            )
            logger.debug(f"Declared output exchange: {output_exchange}")
            
            # Queue for receiving input messages
            self.channel.queue_declare(
                queue=self.input_queue_name, 
                durable=queue_config.get('durable', True)
            )
            
            # Bind queue to input exchange
            self.channel.queue_bind(
                exchange=input_exchange,
                queue=self.input_queue_name,
                routing_key=f"*.{self.agent_id}"  # Accept messages from any source to this agent
            )
            logger.debug(f"Declared and bound input queue: {self.input_queue_name}")
            
            # Set QoS (prefetch count)
            self.channel.basic_qos(
                prefetch_count=queue_config.get('prefetch_count', 1)
            )
            
        except pika.exceptions.ChannelClosedByBroker as e:
            logger.error(f"Channel closed by broker while setting up infrastructure: {e}")
            sys.exit(1)
    
    def register_message_handler(self, handler_func: Callable[[pika.adapters.blocking_connection.BlockingChannel, pika.spec.Basic.Deliver, BasicProperties, bytes], None]) -> None:
        """
        Register a function to handle incoming messages.
        
        Args:
            handler_func (callable): Function to handle messages
        """
        self.message_handler = handler_func
    
    def start_consuming(self) -> None:
        """
        Start consuming messages from the input queue.
        """
        if not self.message_handler:
            logger.error("No message handler registered. Cannot start consuming.")
            return
        
        try:
            self.channel.basic_consume(
                queue=self.input_queue_name,
                on_message_callback=self.message_handler
            )
            logger.debug(f"Started consuming messages from queue: {self.input_queue_name}")
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("Stopping message consumption due to keyboard interrupt")
            self.channel.stop_consuming()
        except Exception as e:
            logger.error(f"Error while consuming messages: {e}")
            self.close()
    
    def send_message(self, exchange: str, routing_key: str, body: str, properties: Optional[BasicProperties] = None) -> bool:
        """
        Send a message to a specified exchange with a routing key.
        
        Args:
            exchange (str): The exchange to publish to
            routing_key (str): The routing key for the message
            body (str): The message body
            properties (pika.BasicProperties, optional): Message properties
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=body,
                properties=properties or pika.BasicProperties(
                    delivery_mode=2  # Persistent message
                )
            )
            logger.debug(f"Sent message to exchange {exchange} with routing key {routing_key}")
            return True
        except (pika.exceptions.AMQPError, Exception) as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def send_result(self, destination: str, result: Dict[str, Any]) -> bool:
        """
        Send simulation results to the specified destination.
        
        Args:
            destination (str): Destination identifier (e.g., 'dt', 'pt')
            result (dict): Result data to be sent
            
        Returns:
            bool: True if successful, False otherwise
        """
        exchanges: Dict[str, str] = self.config.get('exchanges', {})
        output_exchange: str = exchanges.get('output', 'ex.sim.result')
        
        # Prepare the payload with the destination
        payload: Dict[str, Any] = {
            **result,  # Result data
            'source': self.agent_id,  # Agent identifier
            'destinations': [destination]  # Recipient
        }
        
        # Generate message ID
        message_id: str = str(uuid.uuid4())
        
        # Serialize to YAML
        payload_yaml: str = yaml.dump(payload, default_flow_style=False)
        
        # Routing key: <source>.result.<destination>
        routing_key: str = f"{self.agent_id}.result.{destination}"
        
        properties: BasicProperties = pika.BasicProperties(
            delivery_mode=2,  # Persistent message
            content_type='application/x-yaml',
            message_id=message_id
        )
        
        success: bool = self.send_message(output_exchange, routing_key, payload_yaml, properties)
        
        if success:
            logger.debug(f"Sent result to {destination} with message ID: {message_id} and payload: {payload}")
        else:
            logger.error(f"Failed to send result to {destination}")
        
        return success
    
    def close(self) -> None:
        """
        Close the RabbitMQ connection.
        """
        if self.channel and self.channel.is_open:
            try:
                self.channel.stop_consuming()
            except Exception:
                pass
            logger.debug("Stopped consuming messages")
        
        if self.connection and self.connection.is_open:
            self.connection.close()
            logger.info("Closed RabbitMQ connection")