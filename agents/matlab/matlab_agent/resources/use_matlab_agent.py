"""
use_matlab_agent.py

A simple RabbitMQ client to send simulation requests to a MATLAB agent,
and listen asynchronously for the simulation results.
"""

import argparse
import threading
import uuid
from typing import Any, Dict, NoReturn
import pika
import yaml


class SimpleUsageMatlabAgent:
    """
    Simple client class to interact with MATLAB simulation agent via RabbitMQ.

    It loads configuration from YAML, connects to RabbitMQ, sends simulation
    payload requests, and listens for results asynchronously.
    """

    def __init__(
        self,
        agent_identifier: str = "dt",
        destination_identifier: str = "matlab",
        config_path: str = "use.yaml"
    ) -> None:
        """
        Initialize the agent with identifiers and load configuration.

        Args:
            agent_identifier (str): Identifier for this client agent.
            destination_identifier (str): Identifier for the target agent.
            config_path (str): Path to the YAML config file.
        """
        self.agent_id: str = agent_identifier
        self.destination_id: str = destination_identifier

        self.config = self.load_yaml(config_path)
        self.simulation_request_path = self.config.get(
            "simulation_request", "simulation.yaml"
        )
        rabbitmq_cfg = self.config.get("rabbitmq", {})

        credentials = pika.PlainCredentials(
            rabbitmq_cfg.get("username", "guest"),
            rabbitmq_cfg.get("password", "guest"),
        )

        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_cfg.get("host", "localhost"),
                port=rabbitmq_cfg.get("port", 5672),
                virtual_host=rabbitmq_cfg.get("vhost", "/"),
                credentials=credentials,
                heartbeat=rabbitmq_cfg.get("heartbeat", 600),
            )
        )
        self.channel = self.connection.channel()
        self.result_queue: str = ""
        self.setup_channels()

    def setup_channels(self) -> None:
        """
        Declare exchanges and queues, and bind them for message routing.
        """
        self.channel.exchange_declare(
            exchange="ex.bridge.output", exchange_type="topic", durable=True
        )
        self.channel.exchange_declare(
            exchange="ex.sim.result", exchange_type="topic", durable=True
        )

        self.result_queue = f"Q.{self.agent_id}.matlab.result"
        self.channel.queue_declare(queue=self.result_queue, durable=True)

        self.channel.queue_bind(
            exchange="ex.sim.result",
            queue=self.result_queue,
            routing_key=f"{self.destination_id}.result.{self.agent_id}",
        )

        print(f"[{self.agent_id.upper()}] Infrastructure configured successfully.")

    def send_request(self, payload_data: Dict[str, Any]) -> None:
        """
        Send a simulation request message with the given payload.

        Args:
            payload_data (Dict[str, Any]): Simulation payload to send.
        """
        payload: Dict[str, Any] = {
            **payload_data,
            "request_id": str(uuid.uuid4()),
        }

        payload.setdefault("simulation", {})["bridge_meta"] = {
            "protocol": "rabbitmq"
        }
        payload_yaml: str = yaml.dump(payload, default_flow_style=False)
        routing_key: str = f"{self.agent_id}.{self.destination_id}"

        self.channel.basic_publish(
            exchange="ex.bridge.output",
            routing_key=routing_key,
            body=payload_yaml,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                content_type="application/x-yaml",
                message_id=str(uuid.uuid4()),
            ),
        )
        print(f"[{self.agent_id.upper()}] Message sent to matlab: {payload}")

    def handle_result(
        self, ch, method, _properties, body
    ) -> None:
        """
        Callback to process incoming results from MATLAB.

        Args:
            ch: Channel object.
            method: Delivery method.
            _properties: Message properties (unused).
            body: Message body.
        """
        try:
            result: Dict[str, Any] = yaml.safe_load(body)
            print(f"\n[{self.agent_id.upper()}] Result received from MATLAB:")
            print(f"Result: {result}")
            print("-" * 40)
            ch.basic_ack(method.delivery_tag)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Error processing result: {exc}")

    def start_listening(self) -> NoReturn:
        """
        Start consuming messages from the result queue indefinitely.
        """
        self.channel.basic_consume(
            queue=self.result_queue, on_message_callback=self.handle_result
        )
        print(
            f"[{self.agent_id.upper()}] Listening for results on routing key "
            f"'matlab.result.{self.agent_id}'..."
        )
        self.channel.start_consuming()

    def load_yaml(self, file_path: str) -> Dict[str, Any]:
        """
        Load YAML file and return its content as a dictionary.

        Args:
            file_path (str): Path to the YAML file.

        Returns:
            Dict[str, Any]: Parsed YAML content.
        """
        with open(file_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)


def start_listener(agent_identifier: str) -> None:
    """
    Initialize and start the Matlab agent listener in a separate thread.

    Args:
        agent_identifier (str): Agent identifier for the listener.
    """
    matlab_agent = SimpleUsageMatlabAgent(agent_identifier)
    matlab_agent.start_listening()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Simple Matlab Agent Client"
    )
    parser.add_argument(
        "--api-payload",
        type=str,
        default=None,
        help=(
            "Path to the YAML file containing the simulation payload "
            "(simulation.yaml). If omitted, the default path from the "
            "configuration file will be used."
        ),
    )
    args = parser.parse_args()

    AGENT_ID = "dt"
    DESTINATION = "matlab"

    # Start the listener thread to receive simulation results asynchronously.
    listener_thread = threading.Thread(
        target=start_listener,
        args=(AGENT_ID,),
    )
    listener_thread.daemon = True
    listener_thread.start()

    # Instantiate the Matlab agent with the default configuration file.
    agent = SimpleUsageMatlabAgent(
        AGENT_ID,
        DESTINATION,
        config_path="use.yaml",
    )

    try:
        # Determine the simulation payload file to load.
        # Use CLI-specified payload path if provided, otherwise use default from config.
        simulation_file_path = (
            args.api_payload
            if args.api_payload
            else agent.simulation_request_path
        )

        # Load the simulation request data from the specified YAML file.
        simulation_data = agent.load_yaml(simulation_file_path)

        # Send the simulation request to the Matlab agent via RabbitMQ.
        agent.send_request(simulation_data)

        # Keep the main thread alive to continue receiving asynchronous results.
        print("\nPress Ctrl+C to terminate the program...")
        while True:
            pass

    except KeyboardInterrupt:
        print("\nProgram terminated by user.")

    except Exception as exc:  # pylint: disable=broad-except
        print(f"Unexpected error: {exc}")
