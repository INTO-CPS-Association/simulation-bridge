# core.py - Componenti base per il message routing (modificato)
import pika
from utils.logger import get_logger

class RabbitMQConnection:
    def __init__(self, host='localhost'):
        self.connection_params = pika.ConnectionParameters(host)
        self.connection = None
        self.channel = None
    
    def connect(self):
        self.connection = pika.BlockingConnection(self.connection_params)
        self.channel = self.connection.channel()
        return self.channel
    
    def close(self):
        if self.connection and self.connection.is_open:
            self.connection.close()

class InfrastructureManager:
    def __init__(self, channel):
        self.channel = channel
        self.logger = get_logger()

    def setup_exchanges(self, exchanges):
        for exchange in exchanges:
            self.channel.exchange_declare(
                exchange=exchange['name'],
                exchange_type=exchange['type'],
                durable=exchange['durable']
            )
            self.logger.debug(
                "Dichiarato exchange: %s (tipo: %s, durable: %s)",
                exchange['name'],
                exchange['type'],
                exchange['durable']
            )

    def setup_queues(self, queues):
        for queue in queues:
            self.channel.queue_declare(
                queue=queue['name'],
                durable=queue['durable']
            )
            self.logger.debug(
                "Dichiarata coda: %s (durable: %s)",
                queue['name'],
                queue['durable']
            )

    def setup_bindings(self, bindings):
        for binding in bindings:
            self.channel.queue_bind(
                queue=binding['queue'],
                exchange=binding['exchange'],
                routing_key=binding['routing_key']
            )
            self.logger.debug(
                "Creato binding: %s -> %s (%s)",
                binding['queue'],
                binding['exchange'],
                binding['routing_key']
            )

class BaseMessageHandler:
    def __init__(self, channel):
        self.channel = channel
    
    def handle(self, ch, method, properties, body):
        raise NotImplementedError("Deve essere implementato dalle sottoclassi")

    def ack_message(self, ch, delivery_tag):
        ch.basic_ack(delivery_tag)
    
    def nack_message(self, ch, delivery_tag):
        ch.basic_nack(delivery_tag)