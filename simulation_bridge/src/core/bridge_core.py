from blinker import signal
import pika
import json
import paho.mqtt.client as mqtt
import requests
from ..utils.config_manager import ConfigManager
from ..utils.logger import get_logger

logger = get_logger()

class BridgeCore:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager.get_rabbitmq_config()
        self.connection = None
        self.channel = None
        self._initialize_rabbitmq_connection()

        # Get output exchange configuration
        output_exchange = next(
            (ex for ex in self.config['infrastructure']['exchanges'] 
             if ex['name'] == 'ex.bridge.output'),
            None
        )

        if not output_exchange:
            raise ValueError("Output exchange 'ex.bridge.output' not found in configuration")

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
        signal('message_received_input_rabbitmq').connect(self.handle_input_rabbitmq_message)
        signal('message_received_result_rabbitmq').connect(self.handle_result_rabbitmq_message)
        signal('message_received_other_rabbitmq').connect(self.handle_other_rabbitmq_message)
        signal('message_received_input_rest').connect(self.handle_input_rest_message)
        signal('message_received_input_mqtt').connect(self.handle_input_mqtt_message)
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
            logger.error(f"Failed to initialize RabbitMQ connection: {e}")
            raise

    def _ensure_connection(self):
        """Ensure the RabbitMQ connection is active, reconnect if necessary."""
        try:
            if not self.connection or self.connection.is_closed:
                logger.warning("RabbitMQ connection is closed, attempting to reconnect...")
                self._initialize_rabbitmq_connection()
            return True
        except Exception as e:
            logger.error(f"Failed to ensure RabbitMQ connection: {e}")
            return False

    def handle_input_rest_message(self, sender, **kwargs):
        message = kwargs.get('message', {})
        request_id = message.get('simulation', 'unknown').get('request_id', 'unknown')
        producer = kwargs.get('producer', 'unknown')
        consumer = kwargs.get('consumer', 'unknown')
        protocol = "rest"
        logger.info(f"[REST] Handling incoming simulation request with ID: {request_id}")
        self._publish_message(producer, consumer, message, protocol=protocol)

    def handle_input_mqtt_message(self, sender, **kwargs):
        message = kwargs.get('message', {})
        request_id = message.get('simulation', 'unknown').get('request_id', 'unknown')
        producer = kwargs.get('producer', 'unknown')
        consumer = kwargs.get('consumer', 'unknown')
        protocol = "mqtt"
        logger.info(f"[MQTT] Handling incoming simulation request with ID: {request_id}")
        self._publish_message(producer, consumer, message, protocol=protocol)

    def handle_input_rabbitmq_message(self, sender, **kwargs):
        message = kwargs.get('message', {})
        request_id = message.get('simulation', 'unknown').get('request_id', 'unknown')
        producer = kwargs.get('producer', 'unknown')
        consumer = kwargs.get('consumer', 'unknown')
        protocol = "rabbitmq"
        logger.info(f"[RABBITMQ] Handling incoming simulation request with ID: {request_id}")
        self._publish_message(producer, consumer, message, protocol=protocol)

    def handle_result_rabbitmq_message(self, sender, **kwargs):
        message = kwargs.get('message', {})
        bridge_meta = message.get('bridge_meta', {}).get('protocol', 'unknown')
        producer = kwargs.get('message', {}).get('simulation', {}).get('simulator', 'unknown')
        consumer = "result"
        status = message.get('status', 'unknown')
        progress = message.get('progress', {})
        percentage = progress.get('percentage')

        msg = "completed successfully" if status == "completed" else \
            "currently in progress" if status == "in_progress" else status

        percent_info = f" ({percentage}%)" if percentage is not None else ""
        logger.info(f"[STATUS] Simulation {msg}{percent_info}.")

        if bridge_meta == 'rabbitmq':
            self._publish_message(producer, consumer, message, exchange='ex.bridge.result', protocol='rabbitmq')
        if bridge_meta == 'mqtt':
            self._publish_result_message_mqtt(message)
        if bridge_meta == 'rest':
            self._publish_result_message_rest(message)

    def handle_other_rabbitmq_message(self, sender, **kwargs):
        message = kwargs.get('message', {})
        producer = kwargs.get('producer', 'unknown')
        consumer = kwargs.get('consumer', 'unknown')
        queue = kwargs.get('queue', 'unknown')
        logger.info(f"[RABBITMQ] Handling other message from queue {queue}")
        self._publish_message(producer, consumer, message)

    def _publish_message(self, producer, consumer, message, exchange='ex.bridge.output', protocol='rabbitmq'):
        if not self._ensure_connection():
            logger.error("Cannot publish message: RabbitMQ connection is not available")
            return

        routing_key = f"{producer}.{consumer}"
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
            logger.debug(f"Message routed to exchange '{exchange}': {producer} -> {consumer}, protocol={protocol}")
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError) as e:
            logger.error(f"RabbitMQ connection error: {e}")
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
                logger.debug(f"Message routed to exchange '{exchange}' after reconnection: {producer} -> {consumer}")
            except Exception as retry_e:
                logger.error(f"Failed to publish message after reconnection: {retry_e}")
        except Exception as e:
            logger.error(f"Error routing message: {e}")
    
    def _publish_result_message_mqtt(self, message):
        try:
            output_topic = self.mqtt_config['output_topic']
            self.mqtt_client.publish(
                topic=output_topic,
                payload=json.dumps(message),
                qos=self.mqtt_config['qos']
            )
            logger.debug(f"Message published to MQTT topic '{output_topic}, {message}'")
        except Exception as e:
            logger.error(f"Error publishing MQTT message: {e}")

    def _publish_result_message_rest(self, message):
        try:
            # Get the output endpoint and client configuration from config
            client_config = self.rest_config['client']
            output_endpoint = client_config['output_endpoint']
            base_url = client_config['base_url']
            url = f"{base_url}{output_endpoint}"

            # Add bridge metadata
            message['bridge_meta'] = {
                'protocol': 'rest',
                'producer': message.get('simulation', {}).get('id', 'unknown'),
                'consumer': 'result'
            }

            # Send POST request with JSON content
            response = requests.post(
                url,
                json=message,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                logger.debug(f"Successfully sent result message to REST client at {url}")
            else:
                logger.error(f"Failed to send result message to REST client. Status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
        except Exception as e:
            logger.error(f"Error sending result message to REST client: {e}")

    def start(self):
        logger.debug("Simulation Bridge core started")

    def stop(self):
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Bridge core stopped")
        except Exception as e:
            logger.error(f"Error stopping bridge core: {e}") 
