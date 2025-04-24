# simulation_bridge.py - Implementation with logging
from core import RabbitMQConnection, InfrastructureManager, BaseMessageHandler
from config_manager import ConfigManager
from utils.logger import get_logger
import json

logger = get_logger()

import yaml

# Supponiamo che BaseMessageHandler sia una classe di base di cui la tua classe eredità
class SimulationMessageHandler(BaseMessageHandler):
    def handle(self, ch, method, properties, body):
        try:
            source = method.routing_key

            # Carica il corpo del messaggio come YAML
            msg = yaml.safe_load(body)

            # Logga il messaggio ricevuto
            logger.debug(
                "Received message from %s: %s", 
                source, 
                msg,
                extra={'message_id': properties.message_id}
            )

            # Inoltra il messaggio a tutte le destinazioni
            for dest in msg.get('destinations', []):
                routing_key = f"{source}.{dest}"
                self.channel.basic_publish(
                    exchange='ex.bridge.output',
                    routing_key=routing_key,
                    body=body,  # Corpo del messaggio invariato (in YAML)
                    properties=properties
                )
                logger.debug(
                    "Message forwarded to %s", 
                    routing_key,
                    extra={'message_id': properties.message_id}
                )

            # Conferma la ricezione del messaggio
            self.ack_message(ch, method.delivery_tag)
        except yaml.YAMLError as e:
            # Gestione errori YAML (se il corpo del messaggio non è un YAML valido)
            logger.error(
                "YAML decoding error: %s", 
                str(e),
                extra={'body': body, 'delivery_tag': method.delivery_tag}
            )
            self.nack_message(ch, method.delivery_tag)
        except Exception as e:
            # Gestione generica degli errori
            logger.exception(
                "Error processing message: %s", 
                str(e),
                extra={'delivery_tag': method.delivery_tag}
            )
            self.nack_message(ch, method.delivery_tag)

class SimulationBridge:
    def __init__(self):
        self.config = ConfigManager()
        rmq_config = self.config.get_rabbitmq_config()
        
        logger.debug("Initializing RabbitMQ connection")
        self.conn = RabbitMQConnection(host=rmq_config.get('host', 'localhost'))
        self.channel = self.conn.connect()
        self.handler = SimulationMessageHandler(self.channel)
        self.setup_infrastructure()

    def setup_infrastructure(self):
        logger.debug("Configuring RabbitMQ infrastructure")
        infra_config = self.config.get_infrastructure_config()
        
        # Configuring exchanges
        try:
            logger.debug("Configuring exchanges...")
            im = InfrastructureManager(self.channel)
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


    def start(self):
        rmq_config = self.config.get_rabbitmq_config()
        self.channel.basic_qos(prefetch_count=rmq_config.get('prefetch_count', 1))
        
        self.channel.basic_consume(
            queue='Q.bridge.input',
            on_message_callback=self.handler.handle
        )
        logger.info("Bridge Running - Starting message consumption")
        self.channel.start_consuming()