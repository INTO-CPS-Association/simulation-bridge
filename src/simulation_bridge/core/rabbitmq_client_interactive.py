import pika
import yaml
import threading
import time
import json
import logging
from .protocols.rabbitmq.rabbitmq_client import RabbitMQClient  

class SimulationClient:
    REQUEST_QUEUE = 'queue_simulation'
    LIVE_DATA_QUEUE = 'agent_updates'
    
    def __init__(self, config_path='simulation.yml'):
        self.sender = RabbitMQClient(config_path)
        self.listener = RabbitMQClient(config_path)
    
    def load_simulation_data(self, config_file):
        """Load the YAML file and return the data as an OrderedDict."""
        with open(config_file, 'r') as f:
            # Use an OrderedDict to maintain the order
            return yaml.safe_load(f)
    
    def send_simulation_request(self, config_file='simulation_interactive.yml'):
        # Load configuration from YAML file
        sim_request = self.load_simulation_data(config_file)

        # Convert configuration to YAML string with order preserved
        yaml_msg = self.to_yaml(sim_request)

        # Publish the message
        self.sender.publish(self.REQUEST_QUEUE, yaml_msg)
        print(f"[→] Sent simulation data from {config_file}")


    def listen_live_data(self):
        def on_data(ch, method, properties, body):
            """Process received message."""
            try:
                message = body.decode()  # Decode byte message to string
                data = json.loads(message)  # Parse JSON string into data
                print("Received data:\n", data)  # Print received data
            except Exception as e:
                print(f"Error receiving data: {e}")

        self.listener.consume(self.LIVE_DATA_QUEUE, on_data)

        threading.Thread(target=self.listener.start_consuming, daemon=True).start()
        print(f"🟢 Listening on '{self.LIVE_DATA_QUEUE}'...")

    def run(self):
        self.listen_live_data()
        time.sleep(0.5)  # Small delay to ensure the consumer is ready
        self.send_simulation_request()

        print("⏳ Waiting for the simulation to send real-time data...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.sender.close()
            self.listener.close()
            
    def to_yaml(self, data):
        """Converts data to YAML while preserving key order."""
        # Use 'default_flow_style=False' for a readable format
        return yaml.dump(data, default_flow_style=False, sort_keys=False)


if __name__ == '__main__':
    client = SimulationClient()
    client.run()
