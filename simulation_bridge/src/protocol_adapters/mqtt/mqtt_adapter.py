"""MQTT Adapter Module for the Simulation Bridge.

This module implements an adapter for MQTT communication protocol.
"""

import json
import threading
import queue
from typing import Dict, Any

import paho.mqtt.client as mqtt
import yaml
from blinker import signal

from ...utils.config_manager import ConfigManager
from ...utils.logger import get_logger
from ...utils.signal_manager import SignalManager
from ..base.protocol_adapter import ProtocolAdapter

logger = get_logger()


class MQTTAdapter(ProtocolAdapter):
    """MQTT Protocol Adapter implementation.

    This adapter handles MQTT protocol communication, including connecting
    to MQTT brokers, subscribing to topics, and processing incoming messages.
    """

    def _get_config(self) -> Dict[str, Any]:
        """Retrieve MQTT-specific configuration.

        Returns:
            Dict[str, Any]: MQTT configuration dictionary
        """
        return self.config_manager.get_mqtt_config()

    def __init__(self, config_manager: ConfigManager):
        """Initialize the MQTT adapter.

        Args:
            config_manager: Configuration manager instance
        """
        super().__init__(config_manager)
        self.client = mqtt.Client()
        self.topic = self.config['input_topic']
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self._message_queue = queue.Queue()
        self._process_thread = None
        self._client_thread = None
        self._running = False

        self.mqtt_config = config_manager.get_mqtt_config()
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect(
            host=self.mqtt_config['host'],
            port=self.mqtt_config['port'],
            keepalive=self.mqtt_config['keepalive']
        )
        self.mqtt_client.loop_start()

        SignalManager.connect_signal(
            'mqtt',
            'message_received_result_mqtt',
            self.publish_result_message_mqtt)

        logger.debug(
            "MQTT - Adapter initialized with config: host=%s, port=%s, topic=%s",
            self.config['host'], self.config['port'], self.topic)

    def on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker.

        Args:
            client: MQTT client instance
            userdata: User data
            flags: Connection flags
            rc: Result code
        """
        if rc == 0:
            self.client.subscribe(self.topic)
            logger.debug("MQTT - Subscribed to topic: %s", self.topic)
        else:
            logger.error(
                "MQTT - Failed to connect to broker at %s:%s, return code: %s",
                self.config['host'], self.config['port'], rc)

    def on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker.

        Args:
            client: MQTT client instance
            userdata: User data
            rc: Result code
        """
        if rc == 0:
            logger.debug("MQTT - Cleanly disconnected from broker")
        else:
            logger.warning(
                "MQTT - Unexpectedly disconnected from broker with code: %s", rc)

    def on_message(self, client, userdata, msg):
        """Callback for when a message is received from the broker.

        Args:
            client: MQTT client instance
            userdata: User data
            msg: Received message
        """
        try:
            # Try to parse as YAML first, then JSON, then plain text
            try:
                message = yaml.safe_load(msg.payload)
            except Exception:
                try:
                    message = json.loads(msg.payload)
                except Exception:
                    message = {
                        "content": msg.payload.decode('utf-8', errors='replace'),
                        "raw_message": True
                    }

            if not isinstance(message, dict):
                raise ValueError("Message is not a dictionary")

            simulation = message.get('simulation', {})
            producer = simulation.get('client_id', 'unknown')
            consumer = simulation.get('simulator', 'unknown')

            # Put message in queue for processing
            self._message_queue.put((message, producer, consumer))

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("MQTT - Error processing message: %s", exc)

    def _process_messages(self):
        """Process messages in a separate thread."""
        while self._running:
            try:
                message, producer, consumer = self._message_queue.get(
                    timeout=1)
                logger.debug(
                    "MQTT - Processing message %s, from producer: %s, simulator: %s",
                    message, producer, consumer)
                # Use SignalManager to send the signal
                signal('message_received_input_mqtt').send(
                    message=message,
                    producer=producer,
                    consumer=consumer,
                    protocol='mqtt'
                )
            except queue.Empty:
                continue
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("MQTT - Error processing message: %s", exc)

    def _run_client(self):
        """Run the MQTT client in a separate thread."""
        logger.debug("MQTT client thread started")
        try:
            # Connect and start the MQTT client
            logger.debug(
                "MQTT - Attempting to connect to broker with keepalive: %s",
                self.config['keepalive'])

            self.client.connect(
                self.config['host'],
                self.config['port'],
                self.config['keepalive'])

            logger.debug("MQTT - Starting client loop")
            self.client.loop_forever()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("MQTT - Error in client thread: %s", exc)
            self._running = False
            raise

    def start(self) -> None:
        """Start the MQTT adapter.

        Connects to the MQTT broker and starts processing messages.

        Raises:
            Exception: If connection to the broker fails
        """
        logger.debug(
            "MQTT - Starting adapter connection to %s:%s",
            self.config['host'], self.config['port'])

        try:
            # Start message processing thread
            self._running = True
            self._process_thread = threading.Thread(
                target=self._process_messages, daemon=True)
            self._process_thread.start()

            # Start client thread
            self._client_thread = threading.Thread(
                target=self._run_client, daemon=True)
            self._client_thread.start()
            logger.debug("MQTT client thread started successfully")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(
                "MQTT - Error connecting to broker at %s:%s: %s",
                self.config['host'], self.config['port'], exc)
            self.stop()
            raise

    def stop(self) -> None:
        """Stop the MQTT adapter.

        Disconnects from the MQTT broker and stops all processing threads.
        """
        logger.debug("MQTT - Stopping adapter")
        self._running = False
        try:
            SignalManager.disconnect_signal('mqtt', 'message_received_input_mqtt',
                                            self._process_messages)
            self.client.disconnect()
            if self._process_thread and self._process_thread.is_alive():
                self._process_thread.join(timeout=5)
            logger.debug("MQTT - Successfully disconnected from broker")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("MQTT - Error during disconnection: %s", exc)

    def send_result(self, message):
        try:
            output_topic = self.mqtt_config['output_topic']
            self.mqtt_client.publish(
                topic=output_topic,
                payload=json.dumps(message),
                qos=self.mqtt_config['qos']
            )
            logger.debug(
                "Message published to MQTT topic '%s': %s", output_topic, message)
        except (ConnectionError, TimeoutError) as e:
            logger.error("Error publishing MQTT message: %s", e)

    def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming messages (required by ProtocolAdapter).

        Args:
            message: The message to handle
        """
        self.on_message(None, None, message)

    def publish_result_message_mqtt(self, sender, **kwargs):  # pylint: disable=unused-argument
        """
        Publish result message to MQTT topic.

        Args:
            message: Message payload to publish
        """
        try:
            message = kwargs.get('message', {})
            self.send_result(message)
            logger.debug(
                "Succesfully scheduled result message for MQTT client")
        except (ConnectionError, TimeoutError) as e:
            logger.error("Error publishing MQTT message: %s", e)
