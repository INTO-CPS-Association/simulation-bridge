import paho.mqtt.client as mqtt
import time
import json
import yaml
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_path='config.yml'):
    """
    Loads the configuration from the YAML file.
    
    Args:
        config_path (str): Path to the configuration file
        
    Returns:
        dict: Configuration parameters
    """
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            return config
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

def publish_message(topic, payload):
    """
    Creates an MQTT client, connects to the broker, publishes a message, and disconnects.
    
    Args:
        topic (str): MQTT topic to publish to
        payload (str): Message payload to publish
    """
    try:
        # Create and connect client
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        client.connect(broker, port, 60)
        
        # Publish message
        client.loop_start()
        client.publish(topic, payload)
        time.sleep(1)  # Ensure the message is published
        
        # Clean up
        client.loop_stop()
        client.disconnect()
        logger.debug(f"Message published to {topic}: {payload}")
    except Exception as e:
        logger.error(f"Error publishing message: {e}")

def subscribe_and_get_message(topic):
    """
    Connects to the broker, subscribes to the specified topic, waits for a message
    (up to the specified timeout), and returns it as a string.
    
    Args:
        topic (str): MQTT topic to subscribe to
        
    Returns:
        str or None: Received message or None if timeout
    """
    message = None
    
    # Callback for receiving the message
    def on_message(client, userdata, msg):
        nonlocal message
        message = msg.payload.decode()
        client.disconnect()  # Disconnect after receiving the message
    
    try:
        # Create and connect client
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        client.on_message = on_message
        client.connect(broker, port, 60)
        client.subscribe(topic)
        
        # Wait for message with timeout
        t0 = time.time()
        client.loop_start()
        while message is None and (time.time() - t0) < timeout:
            time.sleep(0.1)
        
        # Clean up
        client.loop_stop()
        if client.is_connected():
            client.disconnect()
        
        return message
    except Exception as e:
        logger.error(f"Error subscribing to topic: {e}")
        return None

# Load global configuration
config = load_config()
broker = config['mqtt']['broker']
port = config['mqtt']['port']
input_topic = config['topics']['input_topic']
output_topic = config['topics']['output_topic']
timeout = config.get('timeout', 10)  # Default to 10 if not specified

if __name__ == "__main__":
    # This block acts as an external client to send data and receive the result
    result = subscribe_and_get_message(input_topic)
    if result:
        print("Result received:", result)
    else:
        print("No result received within the timeout.")