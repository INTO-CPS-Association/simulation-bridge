import yaml
import json
import paho.mqtt.client as mqtt
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_path='config.yml'):
    """
    Load configuration from YAML file.
    
    Args:
        config_path (str): Path to the configuration file
        
    Returns:
        dict: Configuration parameters
    """
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

class MQTTCalculator:
    """MQTT service that calculates the product of received values"""
    
    def __init__(self, config_path='config.yml'):
        """
        Initialize the MQTT calculator service.
        
        Args:
            config_path (str): Path to the configuration file
        """
        self.config = load_config(config_path)
        self.broker = self.config['mqtt']['broker']
        self.port = self.config['mqtt']['port']
        self.input_topic = self.config['topics']['input_topic']
        self.output_topic = self.config['topics']['output_topic']
        
        # Setup MQTT client
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        # Set optional authentication if provided in config
        if 'username' in self.config['mqtt'] and 'password' in self.config['mqtt']:
            self.client.username_pw_set(
                self.config['mqtt']['username'],
                self.config['mqtt']['password']
            )

    def on_connect(self, client, userdata, flags, rc, properties=None):
        """
        Callback for successful connection to the MQTT broker.
        
        Args:
            client: MQTT client instance
            userdata: User data
            flags: Connection flags
            rc: Connection result code
            properties: Connection properties (MQTT v5)
        """
        if rc == 0:
            logger.info(f"Connected to {self.broker} with status code {rc}")
            client.subscribe(self.input_topic)
            logger.info(f"Subscribed to {self.input_topic}")
        else:
            logger.error(f"Failed to connect to {self.broker}, return code {rc}")

    def on_message(self, client, userdata, msg):
        """
        Process incoming MQTT messages.
        
        Args:
            client: MQTT client instance
            userdata: User data
            msg: Received message
        """
        try:
            # Decode and parse the JSON payload
            payload = json.loads(msg.payload.decode())
            logger.debug(f"Received message: {payload}")
            
            # Extract values with defaults
            v1 = float(payload.get("value1", 1))
            v2 = float(payload.get("value2", 1))
            v3 = float(payload.get("value3", 1))
            
            # Calculate product
            product = v1 * v2 * v3
            logger.info(f"Received: {payload} → Product: {product}")
            
            # Prepare and publish result
            result = {"product": product}
            self.client.publish(self.output_topic, json.dumps(result))
            logger.info(f"Published to {self.output_topic}: {result}")
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON format in the message")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def run(self):
        """Start the MQTT calculator service"""
        try:
            # Connect to the broker
            logger.info(f"Connecting to MQTT broker {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port)
            
            # Start processing messages
            logger.info("Starting MQTT processing loop")
            self.client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Service stopped by user")
        except Exception as e:
            logger.error(f"Service error: {e}")
        finally:
            # Clean up resources
            self.client.disconnect()
            logger.info("Disconnected from MQTT broker")

if __name__ == "__main__":
    # Create and start the calculator service
    calculator = MQTTCalculator()
    calculator.run()