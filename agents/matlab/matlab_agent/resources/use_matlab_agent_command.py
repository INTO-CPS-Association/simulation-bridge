"""use_matlab_agent_command.py

Simple RabbitMQ client to send control commands (STOP, RUN, CHECK)
 to a MATLAB agent.
"""

import argparse
import ssl
import uuid
from typing import Any, Dict

import pika
import yaml


class MatlabAgentCommandClient:
    """Client to send control commands to the MATLAB agent."""

    def __init__(
        self,
        agent_identifier: str = "dt",
        destination_identifier: str = "matlab",
        config_path: str = "use.yaml",
    ) -> None:
        self.agent_id = agent_identifier
        self.destination_id = destination_identifier

        self.config = self._load_yaml(config_path)
        rabbit_cfg: Dict[str, Any] = self.config.get("rabbitmq", {})

        credentials = pika.PlainCredentials(
            rabbit_cfg.get("username", "guest"),
            rabbit_cfg.get("password", "guest"),
        )

        tls_enabled = bool(rabbit_cfg.get("tls", False))
        ssl_options = None
        port = rabbit_cfg.get("port", 5671 if tls_enabled else 5672)
        if tls_enabled:
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_options = pika.SSLOptions(context, rabbit_cfg.get("host", "localhost"))

        params = pika.ConnectionParameters(
            host=rabbit_cfg.get("host", "localhost"),
            port=port,
            virtual_host=rabbit_cfg.get("vhost", "/"),
            credentials=credentials,
            heartbeat=rabbit_cfg.get("heartbeat", 600),
            ssl_options=ssl_options,
        )

        self.connection = pika.BlockingConnection(params)
        self.channel = self.connection.channel()

        # Exchanges and result queue (used for CHECK)
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

    def send_command(self, command: str, wait_response: bool = False) -> None:
        """Publish the command message and optionally wait for a response."""
        cmd = command.upper()
        self.channel.basic_publish(
            exchange="ex.bridge.output",
            routing_key=f"{self.agent_id}.{self.destination_id}",
            body=yaml.dump({"command": cmd}),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/x-yaml",
                message_id=str(uuid.uuid4()),
            ),
        )
        print(f"[{self.agent_id.upper()}] Sent command '{cmd}'.")

        if wait_response:
            method, _props, body = self.channel.basic_get(
                queue=self.result_queue, auto_ack=True
            )
            if method and body:
                try:
                    response = yaml.safe_load(body)
                    print("Response:", response)
                except yaml.YAMLError:
                    print("Invalid response received")
            else:
                print("No response received.")

    @staticmethod
    def _load_yaml(file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Send control commands to the MATLAB agent"
    )
    parser.add_argument("command", help="Command to send: STOP, RUN, or CHECK")
    parser.add_argument(
        "--config", default="use.yaml", help="YAML configuration file"
    )
    args = parser.parse_args()

    AGENT_ID = "dt"
    DESTINATION = "matlab"

    client = MatlabAgentCommandClient(
        agent_identifier=AGENT_ID,
        destination_identifier=DESTINATION,
        config_path=args.config,
    )

    wait_resp = args.command.upper() == "CHECK"
    client.send_command(args.command, wait_response=wait_resp)
    client.connection.close()
