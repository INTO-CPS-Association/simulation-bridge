import pika
import yaml
import threading
import time
import json
import logging

import pika
import yaml
from typing import Callable, Optional

class RabbitMQClient:
    def __init__(self, config_path: str = 'simulation.yml'):
        """
        Initializes the RabbitMQ client with configuration from a YAML file
        """
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)['rabbitmq']
        
        self.connection = self._create_connection()
        self.channel = self.connection.channel()

    def _create_connection(self) -> pika.BlockingConnection:
        """
        Creates a RabbitMQ connection with parameters from the configuration
        """
        credentials = pika.PlainCredentials(
            self.config['username'],
            self.config['password']
        )

        parameters = pika.ConnectionParameters(
            host=self.config['host'],
            port=self.config['port'],
            virtual_host=self.config['virtual_host'],
            credentials=credentials,
            heartbeat=self.config['heartbeat'],
            blocked_connection_timeout=self.config['blocked_connection_timeout'],
            ssl_options=self._get_ssl_options() if self.config['ssl'] else None
        )

        return pika.BlockingConnection(parameters)

    def _get_ssl_options(self) -> Optional[pika.SSLOptions]:
        """
        Returns SSL options if configured
        """
        if self.config.get('ssl_cafile') and self.config.get('ssl_certfile') and self.config.get('ssl_keyfile'):
            return pika.SSLOptions(
                cafile=self.config['ssl_cafile'],
                certfile=self.config['ssl_certfile'],
                keyfile=self.config['ssl_keyfile']
            )
        return None

    def declare_queue(self, queue_name: str, durable: bool = True):
        """
        Declares a RabbitMQ queue
        """
        self.channel.queue_declare(
            queue=queue_name,
            durable=durable
        )

    def publish(self, queue_name: str, message: str, persistent: bool = True):
        """
        Publishes a message to a queue
        """
        self.channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2 if persistent else 1
            )
        )

    def consume(self, queue_name: str, callback: Callable, auto_ack: bool = False):
        """
        Starts consuming messages from a queue
        """
        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=auto_ack
        )

    def start_consuming(self):
        """
        Starts the infinite loop of message consumption
        """
        self.channel.start_consuming()

    def close(self):
        """
        Closes the RabbitMQ connection
        """
        self.connection.close()

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
    
    def send_simulation_request(self, config_file='simulation_streaming.yml'):
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
