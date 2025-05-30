import pika
import json
from blinker import signal
import yaml
from ...utils.config_manager import ConfigManager
from ...utils.logger import get_logger
import functools
from ..base.protocol_adapter import ProtocolAdapter
from typing import Dict, Any

logger = get_logger()

class RabbitMQAdapter(ProtocolAdapter):
    def _get_config(self) -> Dict[str, Any]:
        return self.config_manager.get_rabbitmq_config()
        
    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        logger.debug(f"RabbitMQ adapter initialized")
        
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.config['host'],
                port=self.config['port'],
                virtual_host=self.config['virtual_host']
            )
        )
        self.channel = self.connection.channel()
        # Get all queues from config and register callback for each
        queues = self.config.get('infrastructure', {}).get('queues', [])
        for queue in queues:
            queue_name = queue.get('name')
            if queue_name:
                cb = functools.partial(self._handle_message, queue_name=queue_name)
                self.channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=cb,
                    auto_ack=False
                )
                logger.debug(f"Subscribed to queue: {queue_name}")
        logger.debug(f"RabbitMQ adapter initialized and subscribed to queues")

    def _handle_message(self, ch, method, properties, body, queue_name):
        try:
            try:
                message = yaml.safe_load(body)
            except Exception:
                try:
                    message = json.loads(body)
                except Exception:
                    message = {
                        "content": body.decode('utf-8', errors='replace'),
                        "raw_message": True
                    }
            if not isinstance(message, dict):
                raise ValueError("Message is not a dictionary")
            simulation = message.get('simulation', {})
            producer = simulation.get('client_id', 'unknown')
            consumer = simulation.get('simulator', 'unknown')

            # Send different signal based on the queue
            if queue_name == 'Q.bridge.input':
                signal_name = 'message_received_input_rabbitmq'
            elif queue_name == 'Q.bridge.result':
                signal_name = 'message_received_result_rabbitmq'
            else:
                signal_name = 'message_received_other_rabbitmq'

            signal(signal_name).send(
                self,
                message=message,
                producer=producer,
                consumer=consumer
            )
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.debug(f"Message processed from queue {queue_name}: {method.routing_key}")
        except Exception as e:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            logger.error(f"Error processing message from {queue_name}: {e}")

    def start(self):
        logger.debug("RabbitMQ adapter started...")
        self.channel.start_consuming()
        
    def stop(self):
        self.connection.close() 
