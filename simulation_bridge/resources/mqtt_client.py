"""MQTT client for simulation bridge communication."""
import os
import json
import time
import yaml
import paho.mqtt.client as mqtt

# MQTT Configuration
MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60
MQTT_INPUT_TOPIC = "bridge/input"
MQTT_OUTPUT_TOPIC = "bridge/output"
MQTT_QOS = 0


def on_message(client, userdata, msg):
    """Callback for received messages.
    
    Args:
        client: MQTT client instance
        userdata: User defined data
        msg: Message object containing topic and payload
    """
    print("\n📥 Message received:")
    print(f"🔹 Topic: {msg.topic}")
    print(f"🔹 Payload: {msg.payload.decode()}")


def send_message_and_listen():
    """Load simulation configuration, send it to the input topic and listen for responses."""
    # Load YAML file
    file_path = os.path.join(os.path.dirname(__file__), 'simulation.yaml')
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            payload = yaml.safe_load(file)
            print("✅ Payload loaded:", payload)
    except Exception as e:
        print(f"❌ Error loading simulation.yaml: {e}")
        return

    client = mqtt.Client()

    # Configure callback for received messages
    client.on_message = on_message

    # Connect to MQTT broker
    client.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)

    # Subscribe to output topic
    client.subscribe(MQTT_OUTPUT_TOPIC, qos=MQTT_QOS)

    # Publish message to bridge/input
    client.publish(MQTT_INPUT_TOPIC, json.dumps(payload), qos=MQTT_QOS)
    print(f"📤 Message published to {MQTT_INPUT_TOPIC}")

    # Start loop to receive messages
    print(f"📡 Listening on {MQTT_OUTPUT_TOPIC}...\n(CTRL+C to terminate)")
    client.loop_forever()


if __name__ == "__main__":
    send_message_and_listen()
