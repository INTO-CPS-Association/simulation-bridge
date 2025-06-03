from blinker import signal
import pika
import json
import paho.mqtt.client as mqtt
import asyncio
from ..utils.config_manager import ConfigManager
from ..utils.logger import get_logger

logger = get_logger()


class BridgeCore:
    def __init__(self, config_manager: ConfigManager, adapters: dict):
        self.config = config_manager.get_rabbitmq_config()
        self.connection = None
        self.channel = None
        self._initialize_rabbitmq_connection()
        self.adapters = adapters

        # Initialize MQTT client
        self.mqtt_config = config_manager.get_mqtt_config()
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect(
            host=self.mqtt_config['host'],
            port=self.mqtt_config['port'],
            keepalive=self.mqtt_config['keepalive']
        )
        self.mqtt_client.loop_start()
        # Get REST configuration
        self.rest_config = config_manager.get_rest_config()
        # Connect different signals to different handlers
        signal('message_received_input_rabbitmq').connect(
            self.handle_input_rabbitmq_message)
        signal('message_received_result_rabbitmq').connect(
            self.handle_result_rabbitmq_message)
        signal('message_received_other_rabbitmq').connect(
            self.handle_other_rabbitmq_message)
        signal('message_received_input_rest').connect(
            self.handle_input_rest_message)
        signal('message_received_input_mqtt').connect(
            self.handle_input_mqtt_message)
        logger.debug("Signals connected and bridge core initialized")

    def _initialize_rabbitmq_connection(self):
        """Initialize or reinitialize the RabbitMQ connection."""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()

            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.config['host'],
                    port=self.config['port'],
                    virtual_host=self.config['virtual_host'],
                    heartbeat=600,  # 10 minutes heartbeat
                    blocked_connection_timeout=300,  # 5 minutes timeout
                    connection_attempts=3,  # Number of connection attempts
                    retry_delay=5  # Delay between retries in seconds
                )
            )
            self.channel = self.connection.channel()
            logger.info("RabbitMQ connection established successfully")
        except Exception as e:
            logger.error("Failed to initialize RabbitMQ connection: %s" % e)
            raise

    def _ensure_connection(self):
        """Ensure the RabbitMQ connection is active, reconnect if necessary."""
        try:
            if not self.connection or self.connection.is_closed:
                logger.warning(
                    "RabbitMQ connection is closed, attempting to reconnect...")
                self._initialize_rabbitmq_connection()
            return True
        except Exception as e:
            logger.error("Failed to ensure RabbitMQ connection: %s" % e)
            return False

    def handle_input_rest_message(self, sender, **kwargs):
        message = kwargs.get('message', {})
        request_id = message.get(
            'simulation',
            'unknown').get(
            'request_id',
            'unknown')
        producer = kwargs.get('producer', 'unknown')
        consumer = kwargs.get('consumer', 'unknown')
        protocol = "rest"
        logger.info(
            "[REST] Handling incoming simulation request with ID: %s" % request_id)
        self._publish_message(producer, consumer, message, protocol=protocol)

    def handle_input_mqtt_message(self, sender, **kwargs):
        message = kwargs.get('message', {})
        request_id = message.get(
            'simulation',
            'unknown').get(
            'request_id',
            'unknown')
        producer = kwargs.get('producer', 'unknown')
        consumer = kwargs.get('consumer', 'unknown')
        protocol = "mqtt"
        logger.info(
            "[MQTT] Handling incoming simulation request with ID: %s" % request_id)
        self._publish_message(producer, consumer, message, protocol=protocol)

    def handle_input_rabbitmq_message(self, sender, **kwargs):
        message = kwargs.get('message', {})
        request_id = message.get(
            'simulation',
            'unknown').get(
            'request_id',
            'unknown')
        producer = kwargs.get('producer', 'unknown')
        consumer = kwargs.get('consumer', 'unknown')
        protocol = "rabbitmq"
        logger.info(
            "[RABBITMQ] Handling incoming simulation request with ID: %s" % request_id)
        self._publish_message(producer, consumer, message, protocol=protocol)

    def handle_result_rabbitmq_message(self, sender, **kwargs):
        message = kwargs.get('message', {})
        bridge_meta = message.get('bridge_meta', {}).get('protocol', 'unknown')
        producer = message.get('source', 'unknown')
        consumer = "result"
        status = message.get('status', 'unknown')
        progress = message.get('progress', {})
        percentage = progress.get('percentage')
        destination = message.get('destinations', [])[0]

        msg = "completed successfully" if status == "completed" else \
            "currently in progress" if status == "in_progress" else status

        percent_info = " (%s%%)" % percentage if percentage is not None else ""
        logger.info("[STATUS] Simulation %s%s." % (msg, percent_info))

        if bridge_meta == 'rabbitmq':
            self._publish_message(
                producer,
                consumer,
                message,
                exchange='ex.bridge.result',
                protocol='rabbitmq')
        if bridge_meta == 'mqtt':
            self._publish_result_message_mqtt(message)
        if bridge_meta == 'rest':
            self._publish_result_message_rest(message, destination)

    def handle_other_rabbitmq_message(self, sender, **kwargs):
        message = kwargs.get('message', {})
        producer = kwargs.get('producer', 'unknown')
        consumer = kwargs.get('consumer', 'unknown')
        queue = kwargs.get('queue', 'unknown')
        logger.info("[RABBITMQ] Handling other message from queue %s" % queue)
        self._publish_message(producer, consumer, message)

    def _publish_message(self, producer, consumer, message,
                         exchange='ex.bridge.output', protocol='rabbitmq'):
        if not self._ensure_connection():
            logger.error(
                "Cannot publish message: RabbitMQ connection is not available")
            return

        routing_key = "%s.%s" % (producer, consumer)
        message['simulation']['bridge_meta'] = {
            'protocol': protocol
        }
        try:
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                )
            )
            logger.debug(
                "Message routed to exchange '%s': %s -> %s, protocol=%s" % (exchange, producer, consumer, protocol))
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError) as e:
            logger.error("RabbitMQ connection error: %s" % e)
            self._initialize_rabbitmq_connection()
            # Retry the publish operation once
            try:
                self.channel.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                    )
                )
                logger.debug(
                    "Message routed to exchange '%s' after reconnection: %s -> %s" % (exchange, producer, consumer))
            except Exception as retry_e:
                logger.error(
                    "Failed to publish message after reconnection: %s" % retry_e)
        except Exception as e:
            logger.error("Error routing message: %s" % e)

    def _publish_result_message_mqtt(self, message):
        try:
            output_topic = self.mqtt_config['output_topic']
            self.mqtt_client.publish(
                topic=output_topic,
                payload=json.dumps(message),
                qos=self.mqtt_config['qos']
            )
            logger.debug(
                "Message published to MQTT topic '%s, %s'" % (output_topic, message))
        except Exception as e:
            logger.error("Error publishing MQTT message: %s" % e)

    def _publish_result_message_rest(self, message, destination):
        try:
            rest_adapter = self.adapters.get('rest')
            if rest_adapter:
                rest_adapter.send_result_sync(destination, message)
                logger.debug(
                    "Successfully scheduled result message for REST client: %s" % destination)
            else:
                logger.error("REST adapter not found")
        except Exception as e:
            logger.error("Error sending result message to REST client: %s" % e)

    def stop(self):
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.debug("Bridge core stopped")
        except Exception as e:
            logger.error("Error stopping bridge core: %s" % e)
