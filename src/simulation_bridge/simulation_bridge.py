# simulation_bridge.py
from .core import RabbitMQConnection, InfrastructureManager, BaseMessageHandler
from .config_manager import ConfigManager
from .utils.logger import get_logger
from typing import Any, Dict
import json
import yaml
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties

logger = get_logger()

class SimulationInputMessageHandler(BaseMessageHandler):
    """Handler for incoming messages from DTs to simulators"""
    def handle(
        self, 
        ch: BlockingChannel, 
        method: Basic.Deliver, 
        properties: BasicProperties, 
        body: bytes
    ) -> None:

        try:
            source: str = method.routing_key

            # Load the message body as YAML
            msg: Dict[str, Any] = yaml.safe_load(body)

            # Log the received message
            logger.debug(
                "Received input message from %s: %s", 
                source, 
                msg,
                extra={'message_id': properties.message_id}
            )

            # Forward the message to all destinations
            for dest in msg.get('destinations', []):
                routing_key: str = f"{source}.{dest}"
                self.channel.basic_publish(
                    exchange='ex.bridge.output',
                    routing_key=routing_key,
                    body=body,  # Message body remains unchanged (in YAML)
                    properties=properties
                )
                logger.debug(
                    "Input message forwarded to %s", 
                    routing_key,
                    extra={'message_id': properties.message_id}
                )

            # Acknowledge the message
            self.ack_message(ch, method.delivery_tag)
        except yaml.YAMLError as e:
            # Handle YAML errors
            logger.error(
                "YAML decoding error: %s", 
                str(e),
                extra={'body': body, 'delivery_tag': method.delivery_tag}
            )
            self.nack_message(ch, method.delivery_tag)
        except Exception as e:
            # Handle generic errors
            logger.exception(
                "Error processing message: %s", 
                str(e),
                extra={'delivery_tag': method.delivery_tag}
            )
            self.nack_message(ch, method.delivery_tag)

class SimulationResultMessageHandler(BaseMessageHandler):
    """Handler for result messages from simulators to DTs"""
    def handle(
        self, 
        ch: BlockingChannel, 
        method: Basic.Deliver, 
        properties: BasicProperties, 
        body: bytes
    ) -> None:
        try:
            # The routing key will be in the format: sim<ID>.result.<destination>
            parts: list[str] = method.routing_key.split('.')
            if len(parts) < 3:
                logger.error(
                    "Invalid routing key format for result message: %s", 
                    method.routing_key,
                    extra={'delivery_tag': method.delivery_tag}
                )
                self.nack_message(ch, method.delivery_tag)
                return
                
            source: str = parts[0]  # simulator
            destination: str = parts[2]  # recipient (dt, pt, etc)
            
            # Load the message body as YAML
            msg: Dict[str, Any] = yaml.safe_load(body)

            # Log the received message
            logger.debug(
                "Received result message from %s to %s: %s", 
                source, 
                destination,
                msg,
                extra={'message_id': properties.message_id}
            )

            # Forward the message to the recipient
            routing_key: str = f"{source}.result"
            self.channel.basic_publish(
                exchange='ex.bridge.result',
                routing_key=routing_key,
                body=body,  # Message body remains unchanged (in YAML)
                properties=properties
            )
            logger.debug(
                "Result message forwarded to %s via %s", 
                destination,
                routing_key,
                extra={'message_id': properties.message_id}
            )

            # Acknowledge the message
            self.ack_message(ch, method.delivery_tag)
        except yaml.YAMLError as e:
            # Handle YAML errors
            logger.error(
                "YAML decoding error in result message: %s", 
                str(e),
                extra={'body': body, 'delivery_tag': method.delivery_tag}
            )
            self.nack_message(ch, method.delivery_tag)
        except Exception as e:
            # Handle generic errors
            logger.exception(
                "Error processing result message: %s", 
                str(e),
                extra={'delivery_tag': method.delivery_tag}
            )
            self.nack_message(ch, method.delivery_tag)

class SimulationBridge:
    def __init__(self) -> None:
        self.config: ConfigManager = ConfigManager()
        rmq_config: Dict[str, Any] = self.config.get_rabbitmq_config()
        
        logger.debug("Initializing RabbitMQ connection")
        self.conn: RabbitMQConnection = RabbitMQConnection(host=rmq_config.get('host', 'localhost'))
        self.channel: BlockingChannel = self.conn.connect()
        
        # Handler for incoming messages (from DTs to simulators)
        self.input_handler: SimulationInputMessageHandler = SimulationInputMessageHandler(self.channel)
        
        # Handler for result messages (from simulators to DTs)
        self.result_handler: SimulationResultMessageHandler = SimulationResultMessageHandler(self.channel)
        
        self.setup_infrastructure()

    def setup_infrastructure(self) -> None:
        logger.debug("Configuring RabbitMQ infrastructure")
        infra_config: Dict[str, Any] = self.config.get_infrastructure_config()
        
        # Configuring exchanges
        try:
            logger.debug("Configuring exchanges...")
            im: InfrastructureManager = InfrastructureManager(self.channel)
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
        rmq_config: Dict[str, Any] = self.config.get_rabbitmq_config()
        self.channel.basic_qos(prefetch_count=rmq_config.get('prefetch_count', 1))
        
        # Consume input messages (from DTs to simulators)
        self.channel.basic_consume(
            queue='Q.bridge.input',
            on_message_callback=self.input_handler.handle
        )
        
        # Consume result messages (from simulators to DTs)
        self.channel.basic_consume(
            queue='Q.bridge.result',
            on_message_callback=self.result_handler.handle
        )
        
        logger.info("Simulation Bridge Running")
        self.channel.start_consuming()