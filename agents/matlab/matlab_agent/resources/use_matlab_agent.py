"""
This is a simple example script to demonstrate how to interact externally with the MATLAB agent.
The script sets up communication channels using RabbitMQ, sends simulation requests to the
MATLAB agent, and listens for results. It uses YAML for message formatting and threading to
handle asynchronous listening.
"""
import threading
import uuid
from typing import Any, Dict, NoReturn
import pika
import yaml


class SimpleUsageMatlabAgent:
    """
    This class facilitates communication with a MATLAB agent via RabbitMQ.
    It allows sending simulation requests and receiving results asynchronously.
    """

    def __init__(self, agent_identifier: str = "dt",
                 destination_identifier: str = "matlab") -> None:
        self.agent_id: str = agent_identifier
        self.destination_id: str = destination_identifier
        self.connection: pika.BlockingConnection = pika.BlockingConnection(
            pika.ConnectionParameters('localhost'))
        self.channel: pika.adapters.blocking_connection.BlockingChannel = self.connection.channel()
        self.result_queue: str = ""
        self.setup_channels()

    def setup_channels(self) -> None:
        """
        Setup exchanges and queues for agent communication
        """
        # Exchange for sending commands to agents
        self.channel.exchange_declare(
            exchange='ex.bridge.output',
            exchange_type='topic',
            durable=True
        )

        # Exchange for receiving results from agents
        self.channel.exchange_declare(
            exchange='ex.sim.result',
            exchange_type='topic',
            durable=True
        )

        # Queue for receiving specific results from MATLAB Agent
        self.result_queue = f'Q.{self.agent_id}.matlab.result'
        self.channel.queue_declare(queue=self.result_queue, durable=True)

        # Bind queue to ex.sim.result with routing key
        # `matlab.result.{agent_id}`
        self.channel.queue_bind(
            exchange='ex.sim.result',
            queue=self.result_queue,
            routing_key=f"{self.destination_id}.result.{self.agent_id}"
        )

        print(f"[{self.agent_id.upper()}] Infrastructure configured successfully.")

    def send_request(self, payload_data: Dict[str, Any]) -> None:
        """
        Send simulation request to MATLAB agent
        """
        # Build payload
        payload: Dict[str, Any] = {
            **payload_data,
            'destinations': ['matlab'],
            'request_id': str(uuid.uuid4())
        }

        # Convert to YAML
        payload_yaml: str = yaml.dump(payload, default_flow_style=False)

        # Routing key: {agent_id}.matlab
        routing_key: str = f"{self.agent_id}.{self.destination_id}"

        # Send message
        self.channel.basic_publish(
            exchange='ex.bridge.output',
            routing_key=routing_key,
            body=payload_yaml,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/x-yaml',
                message_id=str(uuid.uuid4())
            )
        )
        print(f"[{self.agent_id.upper()}] Message sent to matlab: {payload}")

    def handle_result(self,
                      ch: pika.adapters.blocking_connection.BlockingChannel,
                      method: pika.spec.Basic.Deliver,
                      properties: pika.spec.BasicProperties,
                      body: bytes) -> None:
        """
        Handle simulation results
        """
        try:
            result: Dict[str, Any] = yaml.safe_load(body)
            print(f"\n[{self.agent_id.upper()}] Result received from MATLAB:")
            print(f"Result: {result}")
            print("-" * 40)
            ch.basic_ack(method.delivery_tag)

        except yaml.YAMLError as e:
            print(f"YAML Error processing result: {e}")
        except pika.exceptions.AMQPError as e:
            print(f"RabbitMQ Error: {e}")
        except Exception as e:
            print(f"Error processing result: {e}")

    def start_listening(self) -> NoReturn:
        """
        Start listening for simulation results.
        This is a blocking method that runs indefinitely.
        """
        self.channel.basic_consume(
            queue=self.result_queue,
            on_message_callback=self.handle_result
        )
        print(f"[{self.agent_id.upper()}] \
            Listening for results on routing key \
                'matlab.result.{self.agent_id}'...")
        self.channel.start_consuming()

    def load_yaml(self, file_path: str) -> Dict[str, Any]:
        """
        Load YAML file
        """
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)


def start_listener(agent_identifier: str) -> None:
    """
    Start listener in separate thread
    """
    matlab_agent: SimpleUsageMatlabAgent = SimpleUsageMatlabAgent(agent_identifier)
    matlab_agent.start_listening()


if __name__ == "__main__":
    AGENT_ID: str = "dt"
    DESTINATION: str = "matlab"
    # Start listener in separate thread
    listener_thread: threading.Thread = threading.Thread(target=start_listener, args=(AGENT_ID,))
    listener_thread.daemon = True
    listener_thread.start()

    # Create main instance for sending requests
    agent: SimpleUsageMatlabAgent = SimpleUsageMatlabAgent(AGENT_ID, DESTINATION)

    try:
        # Example: You can load simulation data from a YAML file here
        simulation_data: Dict[str, Any] = agent.load_yaml("../api/simulation.yaml")

        # Send simulation request
        agent.send_request(simulation_data)

        print("\nPress Ctrl+C to terminate the program...")
        while True:
            pass

    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    except Exception as e:
        print(f"Error: {e}")
