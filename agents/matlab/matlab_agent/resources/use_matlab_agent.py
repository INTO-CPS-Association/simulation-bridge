import threading
import uuid
from typing import Any, Dict, NoReturn
import pika
import yaml


class SimpleUsageMatlabAgent:
    def __init__(self, agent_identifier: str = "dt",
                 destination_identifier: str = "matlab",
                 config_path: str = "use.yaml") -> None:
        # Store identifiers for the agent and destination
        self.agent_id: str = agent_identifier
        self.destination_id: str = destination_identifier

        # Load configuration from YAML file
        self.config = self.load_yaml(config_path)
        self.simulation_request_path = self.config.get('simulation_request', 'simulation.yaml')
        rabbitmq_cfg = self.config.get('rabbitmq', {})

        # Create RabbitMQ credentials
        credentials = pika.PlainCredentials(
            rabbitmq_cfg.get('username', 'guest'),
            rabbitmq_cfg.get('password', 'guest')
        )

        # Establish connection to RabbitMQ server
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_cfg.get('host', 'localhost'),
                port=rabbitmq_cfg.get('port', 5672),
                virtual_host=rabbitmq_cfg.get('vhost', '/'),
                credentials=credentials,
                heartbeat=rabbitmq_cfg.get('heartbeat', 600)
            )
        )
        self.channel = self.connection.channel()
        self.result_queue: str = ""
        self.setup_channels()

    def setup_channels(self) -> None:
        # Declare exchanges for communication
        self.channel.exchange_declare(
            exchange='ex.bridge.output',
            exchange_type='topic',
            durable=True
        )
        self.channel.exchange_declare(
            exchange='ex.sim.result',
            exchange_type='topic',
            durable=True
        )

        # Create and configure result queue for this agent
        self.result_queue = f'Q.{self.agent_id}.matlab.result'
        self.channel.queue_declare(queue=self.result_queue, durable=True)

        # Bind the queue to the exchange with appropriate routing key
        self.channel.queue_bind(
            exchange='ex.sim.result',
            queue=self.result_queue,
            routing_key=f"{self.destination_id}.result.{self.agent_id}"
        )

        print(f"[{self.agent_id.upper()}] Infrastructure configured successfully.")

    def send_request(self, payload_data: Dict[str, Any]) -> None:
        # Prepare payload with unique request ID
        payload: Dict[str, Any] = {
            **payload_data,
            'request_id': str(uuid.uuid4())
        }

        # Add bridge metadata to the simulation data
        payload.setdefault('simulation', {})['bridge_meta'] = {
            'protocol': 'rabbitmq'
        }
        payload_yaml: str = yaml.dump(payload, default_flow_style=False)
        routing_key: str = f"{self.agent_id}.{self.destination_id}"

        # Publish message to RabbitMQ
        self.channel.basic_publish(
            exchange='ex.bridge.output',
            routing_key=routing_key,
            body=payload_yaml,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                content_type='application/x-yaml',
                message_id=str(uuid.uuid4())
            )
        )
        print(f"[{self.agent_id.upper()}] Message sent to matlab: {payload}")

    def handle_result(self, ch, method, properties, body) -> None:
        # Callback function to process incoming results from MATLAB
        try:
            result: Dict[str, Any] = yaml.safe_load(body)
            print(f"\n[{self.agent_id.upper()}] Result received from MATLAB:")
            print(f"Result: {result}")
            print("-" * 40)
            ch.basic_ack(method.delivery_tag)
        except Exception as e:
            print(f"Error processing result: {e}")

    def start_listening(self) -> NoReturn:
        # Start consuming messages from the result queue
        self.channel.basic_consume(
            queue=self.result_queue,
            on_message_callback=self.handle_result
        )
        print(f"[{self.agent_id.upper()}] Listening for results on routing key "
              f"'matlab.result.{self.agent_id}'...")
        self.channel.start_consuming()

    def load_yaml(self, file_path: str) -> Dict[str, Any]:
        # Helper function to load YAML configuration files
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)


def start_listener(agent_identifier: str) -> None:
    # Function to initialize and run a listener agent in a separate thread
    matlab_agent = SimpleUsageMatlabAgent(agent_identifier)
    matlab_agent.start_listening()


if __name__ == "__main__":
    # Define agent identifiers
    AGENT_ID = "dt"
    DESTINATION = "matlab"

    # Start a listener thread to receive results
    listener_thread = threading.Thread(target=start_listener, args=(AGENT_ID,))
    listener_thread.daemon = True
    listener_thread.start()

    # Create the main agent
    agent = SimpleUsageMatlabAgent(AGENT_ID, DESTINATION)

    try:
        # Load simulation data and send request
        simulation_request_path = agent.simulation_request_path
        simulation_data = agent.load_yaml(simulation_request_path)
        agent.send_request(simulation_data)

        # Keep the main thread running to receive results
        print("\nPress Ctrl+C to terminate the program...")
        while True:
            pass

    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    except Exception as e:
        print(f"Error: {e}")
