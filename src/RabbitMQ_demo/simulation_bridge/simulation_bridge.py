# simulation_bridge.py
from core import RabbitMQConnection, InfrastructureManager, BaseMessageHandler
from config_manager import ConfigManager
from utils.logger import get_logger
import json
import yaml

logger = get_logger()

class SimulationInputMessageHandler(BaseMessageHandler):
    """Handler per i messaggi in ingresso dai DT verso i simulatori"""
    def handle(self, ch, method, properties, body):
        try:
            source = method.routing_key

            # Carica il corpo del messaggio come YAML
            msg = yaml.safe_load(body)

            # Logga il messaggio ricevuto
            logger.debug(
                "Received input message from %s: %s", 
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
                    "Input message forwarded to %s", 
                    routing_key,
                    extra={'message_id': properties.message_id}
                )

            # Conferma la ricezione del messaggio
            self.ack_message(ch, method.delivery_tag)
        except yaml.YAMLError as e:
            # Gestione errori YAML
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

class SimulationResultMessageHandler(BaseMessageHandler):
    """Handler per i messaggi di risultato dai simulatori verso i DT"""
    def handle(self, ch, method, properties, body):
        try:
            # La routing key sarà nel formato: sim<ID>.result.<destination>
            parts = method.routing_key.split('.')
            if len(parts) < 3:
                logger.error(
                    "Invalid routing key format for result message: %s", 
                    method.routing_key,
                    extra={'delivery_tag': method.delivery_tag}
                )
                self.nack_message(ch, method.delivery_tag)
                return
                
            source = parts[0]  # simulatore
            destination = parts[2]  # destinatario (dt, pt, etc)
            
            # Carica il corpo del messaggio come YAML
            msg = yaml.safe_load(body)

            # Logga il messaggio ricevuto
            logger.debug(
                "Received result message from %s to %s: %s", 
                source, 
                destination,
                msg,
                extra={'message_id': properties.message_id}
            )

            # Inoltra il messaggio al destinatario
            routing_key = f"{source}.result"
            self.channel.basic_publish(
                exchange='ex.bridge.result',
                routing_key=routing_key,
                body=body,  # Corpo del messaggio invariato (in YAML)
                properties=properties
            )
            logger.debug(
                "Result message forwarded to %s via %s", 
                destination,
                routing_key,
                extra={'message_id': properties.message_id}
            )

            # Conferma la ricezione del messaggio
            self.ack_message(ch, method.delivery_tag)
        except yaml.YAMLError as e:
            # Gestione errori YAML
            logger.error(
                "YAML decoding error in result message: %s", 
                str(e),
                extra={'body': body, 'delivery_tag': method.delivery_tag}
            )
            self.nack_message(ch, method.delivery_tag)
        except Exception as e:
            # Gestione generica degli errori
            logger.exception(
                "Error processing result message: %s", 
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
        
        # Handler per i messaggi in ingresso (da DT a simulatori)
        self.input_handler = SimulationInputMessageHandler(self.channel)
        
        # Handler per i messaggi di risultato (da simulatori a DT)
        self.result_handler = SimulationResultMessageHandler(self.channel)
        
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
        
        # Consumazione messaggi di input (da DT a simulatori)
        self.channel.basic_consume(
            queue='Q.bridge.input',
            on_message_callback=self.input_handler.handle
        )
        
        # Consumazione messaggi di risultato (da simulatori a DT)
        self.channel.basic_consume(
            queue='Q.bridge.result',
            on_message_callback=self.result_handler.handle
        )
        
        logger.info("Bidirectional Bridge Running")
        self.channel.start_consuming()