import pika
import ssl
import json


class RabbitMQClient:
    def __init__(self, config: dict):
        parameters = pika.ConnectionParameters(
            host=config['host'],
            port=config['port'],
            virtual_host=config.get('virtual_host', '/'),
            credentials=pika.PlainCredentials(config['username'], config['password']),
            heartbeat=config.get('heartbeat', 60),
            blocked_connection_timeout=config.get('blocked_connection_timeout', 300),
            ssl_options=self._build_ssl_options(config) if config.get('ssl') else None
        )
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()

    def _build_ssl_options(self, config):
        context = ssl.create_default_context(
            cafile=config.get('ssl_cafile')
        )
        context.load_cert_chain(
            config.get('ssl_certfile'),
            config.get('ssl_keyfile')
        )
        return pika.SSLOptions(context)

    def declare_queue(self, queue_name: str, durable=True):
        self.channel.queue_declare(queue=queue_name, durable=durable)

    def publish(self, queue: str, message: dict):
        self.channel.basic_publish(exchange='', routing_key=queue, body=json.dumps(message))

    def subscribe(self, queue: str, callback, auto_ack: bool = True):
        self.declare_queue(queue)
        def on_message(ch, method, properties, body):
            callback(body.decode())
        self.channel.basic_consume(queue=queue, on_message_callback=on_message, auto_ack=auto_ack)

    def start_consuming(self):
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.connection.close()

    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()
