import paho.mqtt.client as mqtt
import json
import yaml
from blinker import signal
from ...utils.config_manager import ConfigManager
from ...utils.logger import get_logger
from ..base.protocol_adapter import ProtocolAdapter
from typing import Dict, Any

logger = get_logger()

class MQTTAdapter(ProtocolAdapter):
    def _get_config(self) -> Dict[str, Any]:
        return self.config_manager.get_mqtt_config()
        
    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        self.client = mqtt.Client()
        self.topic = self.config['input_topic']
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        logger.debug(f"MQTT - Adapter initialized with config: host={self.config['host']}, port={self.config['port']}, topic={self.topic}")
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.client.subscribe(self.topic)
            logger.debug(f"MQTT - Subscribed to topic: {self.topic}")
        else:
            logger.error(f"MQTT - Failed to connect to broker at {self.config['host']}:{self.config['port']}, return code: {rc}")
        
    def on_disconnect(self, client, userdata, rc):
        if rc == 0:
            logger.info("MQTT - Cleanly disconnected from broker")
        else:
            logger.warning(f"MQTT - Unexpectedly disconnected from broker with code: {rc}")

    def on_message(self, client, userdata, msg):
        try:
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
            
            logger.debug(f"MQTT - Processing message from producer: {producer}, simulator: {consumer}")
            signal('message_received_input_mqtt').send(
                message=message,
                producer=producer,
                consumer=consumer
            )
        except Exception as e:
            logger.error(f"MQTT - Error processing message: {e}")
        
    def start(self):
        logger.debug(f"MQTT - Starting adapter connection to {self.config['host']}:{self.config['port']}")
        try:
            logger.debug(f"MQTT - Attempting to connect to broker with keepalive: {self.config['keepalive']}")
            self.client.connect(self.config['host'], self.config['port'], self.config['keepalive'])
            logger.debug("MQTT - Starting client loop")
            self.client.loop_forever()
        except Exception as e:
            logger.error(f"MQTT - Error connecting to broker at {self.config['host']}:{self.config['port']}: {e}")
        
    def stop(self):
        logger.info("MQTT - Stopping adapter")
        try:
            self.client.disconnect()
            logger.info("MQTT - Successfully disconnected from broker")
        except Exception as e:
            logger.error(f"MQTT - Error during disconnection: {e}")
            
    def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming messages (required by ProtocolAdapter)"""
        self.on_message(None, None, message) 
