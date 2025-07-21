"""RabbitMQ client for simulation bridge."""
import os
import ssl
import sys
import threading
import uuid
import time
import pika
import yaml


def load_config(config_path="rabbitmq_use.yaml"):
    """Load YAML configuration file."""
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_path}' not found.")
        sys.exit(1)
    except yaml.YAMLError as err:
        print(f"Error parsing YAML file: {err}")
        sys.exit(1)


class RabbitMQClient:
    """Digital Twin client for simulation bridge."""

    def __init__(self, config):
        """Initialize the Digital Twin with the given configuration."""
        self.config = config
        self.dt_id = config['digital_twin']['dt_id']

        rabbitmq_cfg = config['rabbitmq']
        credentials = pika.PlainCredentials(
            username=rabbitmq_cfg['username'],
            password=rabbitmq_cfg['password']
        )
        use_tls = rabbitmq_cfg.get('tls', False)

        if use_tls:
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_options = pika.SSLOptions(context, rabbitmq_cfg['host'])
            parameters = pika.ConnectionParameters(
                host=rabbitmq_cfg['host'],
                port=rabbitmq_cfg.get('port', 5671),
                virtual_host=rabbitmq_cfg.get('vhost', '/'),
                credentials=credentials,
                ssl_options=ssl_options,
                heartbeat=rabbitmq_cfg.get('heartbeat', 600)
            )
        else:
            parameters = pika.ConnectionParameters(
                host=rabbitmq_cfg['host'],
                port=rabbitmq_cfg.get('port', 5672),
                virtual_host=rabbitmq_cfg.get('vhost', '/'),
                credentials=credentials,
                heartbeat=rabbitmq_cfg.get('heartbeat', 600)
            )

        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        self.result_queue_name = None
        self.setup_infrastructure()

    def setup_infrastructure(self):
        """Set up RabbitMQ exchanges and queues."""
        input_ex = self.config['exchanges']['input_bridge']
        result_ex = self.config['exchanges']['bridge_result']
        queue_cfg = self.config['queue']

        # Declare exchanges
        self.channel.exchange_declare(
            exchange=input_ex['name'],
            exchange_type=input_ex['type'],
            durable=input_ex['durable']
        )

        self.channel.exchange_declare(
            exchange=result_ex['name'],
            exchange_type=result_ex['type'],
            durable=result_ex['durable']
        )

        # Declare and bind result queue
        self.result_queue_name = (
            f"{queue_cfg['result_queue_prefix']}."
            f"{self.dt_id}.result"
        )
        self.channel.queue_declare(
            queue=self.result_queue_name, durable=queue_cfg['durable'])
        self.channel.queue_bind(
            exchange=result_ex['name'],
            queue=self.result_queue_name,
            routing_key=queue_cfg['routing_key']
        )

    def send_simulation_request(self, payload_data):
        """Send a simulation request to the bridge."""
        payload = {
            **payload_data
        }

        payload_yaml = yaml.dump(payload, default_flow_style=False)
        routing_key = self.config['digital_twin']['routing_key_send']

        self.channel.basic_publish(
            exchange=self.config['exchanges']['input_bridge']['name'],
            routing_key=routing_key,
            body=payload_yaml,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/x-yaml',
                message_id=str(uuid.uuid4())
            )
        )

    def handle_result(self, channel, method, properties, body):  # pylint: disable=unused-argument
        """Handle incoming simulation results."""
        try:
            source = method.routing_key.split('.')[0]
            result = yaml.safe_load(body)

            print(f"\n[{self.dt_id.upper()}] Received result from {source}:")
            print(f"Result: {result}")
            print("-" * 50)

            channel.basic_ack(method.delivery_tag)

        except yaml.YAMLError as err:
            print(f"Error decoding YAML result: {err}")
            channel.basic_nack(method.delivery_tag)
        except Exception as err:  # pylint: disable=broad-exception-caught
            print(f"Error processing the result: {err}")
            channel.basic_nack(method.delivery_tag)

    def start_listening(self):
        """Start listening for simulation results."""
        self.channel.basic_consume(
            queue=self.result_queue_name,
            on_message_callback=self.handle_result
        )
        print(f" [{self.dt_id.upper()}] Listening for simulation results...")
        self.channel.start_consuming()

    @staticmethod
    def load_yaml_file(file_path):
        """Load and parse a YAML file."""
        with open(file_path, 'r', encoding="utf-8") as file:
            return yaml.safe_load(file)


def start_dt_listener(config):
    """Start a Digital Twin listener in a separate thread."""
    dt = RabbitMQClient(config)
    dt.start_listening()


def main():
    """Main program entry point."""
    config = load_config()

    # Start listener thread
    listener_thread = threading.Thread(
        target=start_dt_listener, args=(config,))
    listener_thread.daemon = True
    listener_thread.start()

    # Create digital twin and send simulation request
    dt = RabbitMQClient(config)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_file_path = os.path.join(base_dir, config['payload_file'])

    try:
        simulation_payload = dt.load_yaml_file(yaml_file_path)
        dt.send_simulation_request(simulation_payload)

        print("\nPress Ctrl+C to terminate the program...")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nProgram terminated by the user.")
    except Exception as err:  # pylint: disable=broad-exception-caught
        print(f"Error: {err}")


if __name__ == "__main__":
    main()
