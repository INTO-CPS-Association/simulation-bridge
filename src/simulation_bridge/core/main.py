import yaml
import paho.mqtt.client as mqtt
import json
import logging
from typing import Dict, Any
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, '..', '..', 'config', 'config.yml')

with open(config_path) as f:
    config = yaml.safe_load(f)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = config_path) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Dictionary containing configuration parameters
    """
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

def on_connect(client, userdata, flags, reason_code, properties):
    """
    Callback function for MQTT connection events.
    
    Args:
        client: MQTT client instance
        userdata: User data
        flags: Connection flags
        reason_code: Connection result code
        properties: Connection properties
    """
    if reason_code == 0:
        logger.info("Successfully connected to MQTT broker!")
        # Subscribe to all output topics
        for sim_name, sim_config in userdata['simulations'].items():
            output_topic = sim_config['output_topic']
            client.subscribe(output_topic)
            logger.info(f"Subscribed to: {output_topic}")
        
        # Send data to all input topics
        send_data_to_simulators(client, userdata['simulations'])
    else:
        logger.error(f"Connection failed: {reason_code}")

def on_message(client, userdata, msg):
    """
    Callback function for handling incoming MQTT messages.
    
    Args:
        client: MQTT client instance
        userdata: User data
        msg: Received message
    """
    # Identify the simulation from the topic
    simulator = next(
        (sim_name for sim_name, sim_config in userdata['simulations'].items()
         if msg.topic == sim_config['output_topic']),
        None
    )
    
    topic_info = f"{simulator.upper()} ({msg.topic})" if simulator else f"unknown topic: {msg.topic}"
    logger.info(f"Received message from {topic_info}")
    
    try:
        payload = json.loads(msg.payload.decode())
        logger.info(f"Payload: {json.dumps(payload, indent=4)}")
    except json.JSONDecodeError:
        logger.info(f"Raw payload: {msg.payload.decode()}")

def send_data_to_simulators(client, simulations):
    """
    Send test data to all simulation input topics.
    
    Args:
        client: MQTT client instance
        simulations: Dictionary of simulation configurations
    """
    data = {
        "value1": 3.5,
        "value2": 2.1,
        "value3": 4.7
    }
    
    for sim_name, sim_config in simulations.items():
        input_topic = sim_config['input_topic']
        client.publish(input_topic, json.dumps(data))
        logger.info(f"Data sent to {sim_name} ({input_topic})")

def main():
    """
    Main function to initialize and run the MQTT client.
    """
    try:
        # Load configuration
        config = load_config()
        
        # MQTT Configuration
        broker = config['mqtt']['broker']
        port = config['mqtt']['port']
        timeout = config.get('timeout', 10)
        simulations = config['simulations']
        
        # Initialize client with userdata
        userdata = {
            'simulations': simulations
        }
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata=userdata)
        
        # Assign callbacks
        client.on_connect = on_connect
        client.on_message = on_message
        
        # Connect and loop
        logger.info(f"Connecting to {broker}:{port}...")
        client.connect(broker, port, timeout)
        logger.info("Connected to MQTT broker")
        client.loop_forever()
        
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Application error: {e}")

if __name__ == "__main__":
    main()