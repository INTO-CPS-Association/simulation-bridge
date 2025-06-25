"""MQTT Client for simulation bridge."""

import os
import ssl
import json
import sys
import yaml
import paho.mqtt.client as mqtt


def load_config(config_path="mqtt_use.yaml"):
    """Load YAML configuration file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        dict: Configuration data.

    Raises:
        SystemExit: If the file cannot be found or parsed.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_path}' not found.")
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"Error parsing YAML file: {exc}")
        sys.exit(1)


class MQTTClient:
    """MQTT Client for handling simulation data."""

    def __init__(self, config):
        """Initialize the MQTT client.

        Args:
            config: Dictionary containing configuration data.
        """
        self.config = config['mqtt']
        self.payload_file = config.get('payload_file', 'simulation.yaml')
        self.client = mqtt.Client()
        self.client.username_pw_set(
            self.config['username'],
            self.config['password']
        )
        if self.config.get('tls', False):
            self.client.tls_set(
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT
            )
            self.client.tls_insecure_set(False)
        self.client.on_message = self.on_message

    def on_message(self, client, userdata, msg):  # pylint: disable=unused-argument
        """Callback for received messages.

        Args:
            client: MQTT client instance.
            userdata: User data.
            msg: Message received.
        """
        print("\n📥 Message received:")
        print(f"🔹 Topic: {msg.topic}")
        print(f"🔹 Payload: {msg.payload.decode()}")

    def create_request(self):
        """Load payload from YAML file.

        Returns:
            dict: Payload data.

        Raises:
            SystemExit: If the file cannot be loaded.
        """
        file_path = os.path.join(
            os.path.dirname(
                os.path.abspath(__file__)),
            self.payload_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                payload = yaml.safe_load(file)
                print("✅ Payload loaded:", payload)
                return payload
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"❌ Error loading {self.payload_file}: {exc}")
            sys.exit(1)

    def connect_and_listen(self):
        """Connect to MQTT broker, publish payload, and listen for messages."""
        self.client.connect(
            self.config['host'],
            self.config['port'],
            self.config['keepalive']
        )

        # Subscribe to output topic
        self.client.subscribe(
            self.config['output_topic'],
            qos=self.config['qos'])

        # Publish payload to input topic
        payload = self.create_request()
        self.client.publish(
            self.config['input_topic'],
            json.dumps(payload),
            qos=self.config['qos']
        )
        print(f"📤 Message published to {self.config['input_topic']}")

        print(
            f"""📡 Listening on {
                self.config['output_topic']}...\n(CTRL+C to terminate)""")
        self.client.loop_forever()


if __name__ == "__main__":
    CONFIG = load_config()
    MQTT_CLIENT = MQTTClient(CONFIG)
    MQTT_CLIENT.connect_and_listen()
