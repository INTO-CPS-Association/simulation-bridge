import paho.mqtt.client as mqtt
import time
import json  # For working with JSON
import yaml  # For reading the YAML configuration file

# Function to load the configuration from the YAML file
def load_config(config_path='config.yml'):
    """
    Loads the configuration from the YAML file.
    """
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

# Load the configuration
config = load_config()

# Extract parameters from the configuration
broker = config['mqtt']['broker']
port = config['mqtt']['port']
input_topic = config['topics']['input_topic']
output_topic = config['topics']['output_topic']
timeout = config.get('timeout', 10)  # Default to 10 if not specified

def publish_message(topic, payload):
    """
    Creates an MQTT client, connects to the broker, publishes a message, and disconnects.
    """
    client = mqtt.Client()
    client.connect(broker, port, 60)
    client.loop_start()
    client.publish(topic, payload)
    time.sleep(1)  # Ensure the message is published
    client.loop_stop()
    client.disconnect()

def subscribe_and_get_message(topic):
    """
    Connects to the broker, subscribes to the specified topic, waits for a message 
    (up to the specified timeout), and returns it as a string.
    """
    message = None

    # Callback for receiving the message
    def on_message(client, userdata, msg):
        nonlocal message
        message = msg.payload.decode()
        client.disconnect()  # Disconnect after receiving the message

    client = mqtt.Client()
    client.on_message = on_message
    client.connect(broker, port, 60)
    client.subscribe(topic)
    
    t0 = time.time()
    client.loop_start()
    while message is None and (time.time() - t0) < timeout:
        time.sleep(0.1)
    client.loop_stop()
    if client.is_connected():
        client.disconnect()
    
    return message

if __name__ == "__main__":
    # This block acts as an external client to send data and receive the result from the MATLAB simulation.
    
    result = subscribe_and_get_message(input_topic)
    
    if result:
        print("Result received:", result)
    else:
        print("No result received within the timeout.")
