"""
use_matlab_agent_streaming.py

RabbitMQ client to send streaming simulation requests to a MATLAB agent
and receive real-time results asynchronously.
"""

import argparse
import ssl
import threading
import time
import uuid
from typing import Any, Dict

import pika
import yaml


class StreamingUsageMatlabAgent:
    """Client for interacting with the MATLAB simulation agent via RabbitMQ."""

    def __init__(
        self,
        agent_identifier: str = "dt",
        destination_identifier: str = "matlab",
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
            ssl_options = pika.SSLOptions(context, rabbitmq_cfg.get("host", "localhost"))

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
        """Declare exchanges, queues and bindings."""
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
        print(f"[{self.agent_id.upper()}] Infrastructure ready.")

    def send_request(self, payload_data: Dict[str, Any]) -> None:
        """Send a simulation request."""
        payload = {**payload_data, "request_id": str(uuid.uuid4())}
        payload.setdefault("simulation", {})["bridge_meta"] = {"protocol": "rabbitmq"}

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
        print(f"[{self.agent_id.upper()}] Request sent → MATLAB (routing key "
              f"{self.agent_id}.{self.destination_id}).")

    def _handle_result(self, ch, method, _properties, body):  # noqa: D401, N802
        """Callback for simulation results."""
        try:
            result = yaml.safe_load(body)
            print(f"\n[{self.agent_id.upper()}] Result received:")
            print(result)
            print("-" * 40)
            ch.basic_ack(method.delivery_tag)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Error processing result: {exc}")
            ch.basic_nack(method.delivery_tag)

    def start_listening(self) -> None:
        """Begin consuming results (blocking)."""
        self.channel.basic_consume(
            queue=self.result_queue, on_message_callback=self._handle_result
        )
        print(f"[{self.agent_id.upper()}] Waiting for results "
              f"(binding key '{self.destination_id}.result.{self.agent_id}')…")
        self.channel.start_consuming()

    @staticmethod
    def _load_yaml(file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as fp:
            return yaml.safe_load(fp)


def _listener_thread(agent_identifier: str, config_path: str) -> None:
    StreamingUsageMatlabAgent(agent_identifier, config_path=config_path).start_listening()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MATLAB Simulation RabbitMQ Client")
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

    AGENT_ID = "dt"
    DESTINATION = "matlab"

    # ---- Listener thread
    threading.Thread(
        target=_listener_thread,
        args=(AGENT_ID, args.config),
        daemon=True,
    ).start()

    # ---- Sender
    client = StreamingUsageMatlabAgent(
        AGENT_ID,
        DESTINATION,
        config_path=args.config,
    )

    try:
        payload_path = args.payload or client.simulation_request_path
        simulation_payload = client._load_yaml(payload_path)
        client.send_request(simulation_payload)

        print("\nPress Ctrl+C to exit...")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nTerminated by user.")

    except Exception as exc:  # pylint: disable=broad-except
        print(f"Unexpected error: {exc}")
