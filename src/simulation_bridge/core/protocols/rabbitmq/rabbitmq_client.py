import pika
import yaml
from typing import Callable, Optional

class RabbitMQClient:
    def __init__(self, config_path: str = 'simulation.yml'):
        """
        Initializes the RabbitMQ client with configuration from a YAML file
        """
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)['rabbitmq']
        
        self.connection = self._create_connection()
        self.channel = self.connection.channel()

    def _create_connection(self) -> pika.BlockingConnection:
        """
        Creates a RabbitMQ connection with parameters from the configuration
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
        Returns SSL options if configured
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
        Declares a RabbitMQ queue
        """
        self.channel.queue_declare(
            queue=queue_name,
            durable=durable
        )

    def publish(self, queue_name: str, message: str, persistent: bool = True):
        """
        Publishes a message to a queue
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
        Starts consuming messages from a queue
        """
        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=auto_ack
        )

    def start_consuming(self):
        """
        Starts the infinite loop of message consumption
        """
        self.channel.start_consuming()

    def close(self):
        """
        Closes the RabbitMQ connection
        """
        self.connection.close()
