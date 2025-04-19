import pika
import yaml
from typing import Callable, Optional

class RabbitMQClient:
    def __init__(self, config_path: str = 'simulation.yml'):
        """
        Inizializza il client RabbitMQ con configurazione da YAML
        """
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)['rabbitmq']
        
        self.connection = self._create_connection()
        self.channel = self.connection.channel()

    def _create_connection(self) -> pika.BlockingConnection:
        """
        Crea una connessione RabbitMQ con parametri dalla configurazione
        """
        credentials = pika.PlainCredentials(
            self.config['username'],
            self.config['password']
        )

        parameters = pika.ConnectionParameters(
            host=self.config['host'],
            port=self.config['port'],
            virtual_host=self.config['virtual_host'],
            credentials=credentials,
            heartbeat=self.config['heartbeat'],
            blocked_connection_timeout=self.config['blocked_connection_timeout'],
            ssl_options=self._get_ssl_options() if self.config['ssl'] else None
        )

        return pika.BlockingConnection(parameters)

    def _get_ssl_options(self) -> Optional[pika.SSLOptions]:
        """
        Restituisce le opzioni SSL se configurate
        """
        if self.config.get('ssl_cafile') and self.config.get('ssl_certfile') and self.config.get('ssl_keyfile'):
            return pika.SSLOptions(
                cafile=self.config['ssl_cafile'],
                certfile=self.config['ssl_certfile'],
                keyfile=self.config['ssl_keyfile']
            )
        return None

    def declare_queue(self, queue_name: str, durable: bool = True):
        """
        Dichiarazione di una coda RabbitMQ
        """
        self.channel.queue_declare(
            queue=queue_name,
            durable=durable
        )

    def publish(self, queue_name: str, message: str, persistent: bool = True):
        """
        Pubblica un messaggio su una coda
        """
        self.channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2 if persistent else 1
            )
        )

    def consume(self, queue_name: str, callback: Callable, auto_ack: bool = False):
        """
        Avvia il consumo di messaggi da una coda
        """
        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=auto_ack
        )

    def start_consuming(self):
        """
        Avvia il loop infinito di consumo messaggi
        """
        self.channel.start_consuming()

    def close(self):
        """
        Chiude la connessione RabbitMQ
        """
        self.connection.close()