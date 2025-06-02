import pika
from ..utils.config_manager import ConfigManager
from ..utils.logger import get_logger

logger = get_logger()


class RabbitMQInfrastructure:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager.get_rabbitmq_config()
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.config['host'],
                port=self.config['port'],
                virtual_host=self.config['virtual_host']
            )
        )
        self.channel = self.connection.channel()

    def setup(self):
        """Setup all exchanges, queues and bindings"""
        try:
            self._setup_exchanges()
            self._setup_queues()
            self._setup_bindings()
            logger.info(
                "Simulation Bridge infrastructure setup completed successfully")
        except Exception as e:
            logger.error("Error setting up RabbitMQ infrastructure: %s", e)
            raise
        finally:
            self.connection.close()

    def _setup_exchanges(self):
        """Declare all exchanges"""
        for exchange in self.config['infrastructure']['exchanges']:
            try:
                self.channel.exchange_declare(
                    exchange=exchange['name'],
                    exchange_type=exchange['type'],
                    durable=exchange['durable'],
                    auto_delete=exchange['auto_delete'],
                    internal=exchange['internal']
                )
                logger.debug("Exchange declared: %s", exchange['name'])
            except Exception as e:
                logger.error(
                    "Error declaring exchange %s: %s",
                    exchange['name'], e)
                raise

    def _setup_queues(self):
        """Declare all queues"""
        for queue in self.config['infrastructure']['queues']:
            try:
                self.channel.queue_declare(
                    queue=queue['name'],
                    durable=queue['durable'],
                    exclusive=queue['exclusive'],
                    auto_delete=queue['auto_delete']
                )
                logger.debug("Queue declared: %s", queue['name'])
            except Exception as e:
                logger.error("Error declaring queue %s: %s", queue['name'], e)
                raise

    def _setup_bindings(self):
        """Setup all queue-exchange bindings"""
        for binding in self.config['infrastructure']['bindings']:
            try:
                self.channel.queue_bind(
                    exchange=binding['exchange'],
                    queue=binding['queue'],
                    routing_key=binding['routing_key']
                )
                logger.debug(
                    "Binding created: %s -> %s (%s)",
                    binding['queue'], binding['exchange'], binding['routing_key'])
            except Exception as e:
                logger.error(
                    "Error creating binding %s -> %s: %s",
                    binding['queue'], binding['exchange'], e)
                raise
