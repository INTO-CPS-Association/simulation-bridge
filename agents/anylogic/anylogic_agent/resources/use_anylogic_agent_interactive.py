"""
use_anylogic_agent_interactive.py

RabbitMQ client to send interactive simulation requests to ANYLOGIC Agent
and receive results asynchronously. When the agent returns
{"status": "completed"} the program terminates automatically.
"""

import argparse
import os
import ssl
import sys
import uuid
from typing import Any, Dict

import pika
import yaml


class InteractiveUsageAnylogicAgent:
    """Client for interacting with the anylogic simulation agent via RabbitMQ (interactive mode)."""

    def __init__(
        self,
        agent_identifier: str = "dt",
        destination_identifier: str = "anylogic",
        config_path: str = "use.yaml",
    ) -> None:
        self.agent_id: str = agent_identifier
        self.destination_id: str = destination_identifier

        # --- Load configuration
        self.config = self._load_yaml(config_path)
        self.simulation_request_path: str = self.config.get(
            "simulation_request", "simulation.yaml"
        )
        rabbitmq_cfg: Dict[str, Any] = self.config.get("rabbitmq", {})

        # --- Credentials
        credentials = pika.PlainCredentials(
            rabbitmq_cfg.get("username", "guest"),
            rabbitmq_cfg.get("password", "guest"),
        )

        # --- TLS / non-TLS parameters
        tls_enabled: bool = bool(rabbitmq_cfg.get("tls", False))
        ssl_options = None
        port = rabbitmq_cfg.get("port", 5671 if tls_enabled else 5672)

        if tls_enabled:
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_options = pika.SSLOptions(
                context, rabbitmq_cfg.get("host", "localhost")
            )

        connection_params = pika.ConnectionParameters(
            host=rabbitmq_cfg.get("host", "localhost"),
            port=port,
            virtual_host=rabbitmq_cfg.get("vhost", "/"),
            credentials=credentials,
            heartbeat=rabbitmq_cfg.get("heartbeat", 600),
            ssl_options=ssl_options,
        )

        # --- Establish connection / channel
        self.connection = pika.BlockingConnection(connection_params)
        self.channel = self.connection.channel()

        # --- Infrastructure
        self.result_queue: str = ""
        self._setup_channels()

    def _setup_channels(self) -> None:
        self.channel.exchange_declare(
            exchange="ex.bridge.output", exchange_type="topic", durable=True
        )
        self.channel.exchange_declare(
            exchange="ex.sim.result", exchange_type="topic", durable=True
        )
        self.channel.exchange_declare(
            exchange="ex.input.stream", exchange_type="topic", durable=True
        )

        self.result_queue = f"Q.{self.agent_id}.anylogic.result"
        self.channel.queue_declare(queue=self.result_queue, durable=True)
        self.channel.queue_bind(
            exchange="ex.sim.result",
            queue=self.result_queue,
            routing_key=f"{self.destination_id}.result.{self.agent_id}",
        )
        print(f"[{self.agent_id.upper()}] Infrastructure ready.")

    def send_request(self, payload_data: Dict[str, Any], request_id: str) -> None:
        payload = {**payload_data}
        payload.setdefault("simulation", {})["request_id"] = request_id
        payload["simulation"].setdefault("bridge_meta", {})["protocol"] = "rabbitmq"

        self.channel.basic_publish(
            exchange="ex.bridge.output",
            routing_key=f"{self.agent_id}.{self.destination_id}",
            body=yaml.dump(payload, default_flow_style=False),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/x-yaml",
                message_id=str(uuid.uuid4()),
            ),
        )
        print(f"[{self.agent_id.upper()}] Interactive request sent → anylogic "
              f"(routing key {self.agent_id}.{self.destination_id}).")

    def stream_inputs(self, request_id: str, stream_key: str) -> None:
        """
        Continuously sends input messages to AnyLogic simulation until completion.
        Adjust the message structure as needed for your AnyLogic model.
        """
        print(f"[INPUT STREAM] Publishing messages on '{stream_key}' …")
        try:
            while True:
                msg = {
                    "type": "command to be executed",
                    "data": {
                        "variable": input("Which variable do you want to change: conveyorTargetState, conveyor1TargetState, conveyor2TargetState, conveyor3TargetState, executionTime? "),
                        "state": input("active/not active for conveyorTargetState or low/medium/high for executionTime: ")
                        }                            
                }
                self.channel.basic_publish(
                    exchange="ex.input.stream",
                    routing_key=stream_key,
                    body=yaml.dump(msg),
                    properties=pika.BasicProperties(
                        content_type="application/x-yaml",
                        message_id=str(uuid.uuid4()),
                    ),
                )
                if getattr(self, "_stop_stream", False):
                    print("[INPUT STREAM] Received stop signal, ending input stream.")
                    break
        except Exception as exc:
            print(f"[INPUT STREAM] Error: {exc}")
        print("[INPUT STREAM] Input loop finished.")

    def _handle_result(self, ch, method, _props, body):  # noqa: N802
        """Handle incoming simulation messages."""
        try:
            result = yaml.safe_load(body)
            print(f"\n[{self.agent_id.upper()}] Result received:")
            print(result)
            print("-" * 40)

            ch.basic_ack(method.delivery_tag)

            # Terminate on completed status
            if result.get("status") == "completed":
                print(
                    f"[{self.agent_id.upper()}] Simulation completed successfully.")
                self._stop_stream = True
                self._shutdown()

        except Exception as exc:  # pylint: disable=broad-except
            print(f"Error processing result: {exc}")
            ch.basic_nack(method.delivery_tag)

    def start_listening(self) -> None:
        self.channel.basic_consume(
            queue=self.result_queue, on_message_callback=self._handle_result
        )
        print(f"[{self.agent_id.upper()}] Waiting for results "
              f"(binding key '{self.destination_id}.result.{self.agent_id}')…")
        self.channel.start_consuming()

    def _shutdown(self) -> None:
        """Gracefully stop consuming, close the connection and exit."""
        try:
            # Stop RabbitMQ consumer loop
            self.channel.stop_consuming()
        except Exception:   # channel might already be closing
            pass

        try:
            self.connection.close()
        except Exception:
            pass

        print(f"[{self.agent_id.upper()}] Connection closed. Exiting…")
        # Ensure all threads exit – use os._exit to terminate the whole process
        os._exit(0)

    @staticmethod
    def _load_yaml(file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as fp:
            return yaml.safe_load(fp)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="anylogic Interactive Simulation RabbitMQ Client")
    parser.add_argument(
        "--config",
        default="use.yaml",
        help="YAML configuration file (default: use.yaml)",
    )
    parser.add_argument(
        "--payload",
        default=None,
        help="YAML payload to send (overrides 'simulation_request' in config)",
    )
    args = parser.parse_args()

    AGENT_ID = "dt_anylogic"
    DESTINATION = "anylogic"

    # Create client
    client = InteractiveUsageAnylogicAgent(
        AGENT_ID,
        DESTINATION,
        config_path=args.config,
    )

    try:
        # Load and send simulation request
        payload_path = args.payload or client.simulation_request_path
        simulation_payload = client._load_yaml(payload_path)
        request_id = str(uuid.uuid4())

        # Extract stream key from payload
        stream_source = simulation_payload["simulation"]["inputs"]["stream_source"]
        stream_key = stream_source.replace("rabbitmq://", "")

        client.send_request(simulation_payload, request_id)

        # Start listening for results in a background thread
        import threading
        client._stop_stream = False
        listener_thread = threading.Thread(target=client.start_listening, daemon=True)
        #listener_thread.start()

        # Start input streaming in the main thread
        client.stream_inputs(request_id, stream_key)

    except KeyboardInterrupt:
        print("\nTerminated by user.")
        try:
            client._shutdown()
        except Exception:   # best-effort cleanup
            pass
        sys.exit(0)
    except Exception as exc:    # pylint: disable=broad-except
        print(f"Unexpected error: {exc}")
        sys.exit(1)