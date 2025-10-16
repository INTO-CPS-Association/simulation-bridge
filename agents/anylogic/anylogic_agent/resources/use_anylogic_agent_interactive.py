"""
use_anylogic_agent_interactive.py

Asynchronous RabbitMQ client for sending interactive simulation requests
to the AnyLogic agent
"""

import argparse
import asyncio
import ssl
import uuid
from typing import Any, Dict

import anyio
import yaml
from aio_pika import (
    connect_robust,
    ExchangeType,
    Message,
    DeliveryMode,
)


class InteractiveUsageAnylogicAgent:
    """
    Asynchronous client that interacts with a AnyLogic agent for running interactive simulations.
    This class connects to RabbitMQ, sends requests to the AnyLogic agent, streams input frames,
    and processes the results.
    """

    def __init__(self, agent_id: str, destination_id: str,
                 rabbitmq_cfg: Dict[str, Any]) -> None:
        """
        Initializes the agent with necessary identifiers and configuration.
        Sets up the result queue for receiving simulation results.
        """
        self.agent_id = agent_id
        self.destination_id = destination_id
        self.cfg = rabbitmq_cfg
        # Queue to receive results
        self.result_queue = f"Q.{agent_id}.anylogic.result"
        # Event to stop the stream when the simulation ends
        self.stop_event = asyncio.Event()

    async def setup(self) -> None:
        """
        Connects to RabbitMQ, declares necessary exchanges and queues for sending/receiving messages.
        This includes setting up TLS if enabled in the configuration.
        """
        tls_enabled: bool = bool(self.cfg.get("tls", False))
        # Default port is 5671 for TLS, 5672 otherwise
        port = self.cfg.get("port", 5671 if tls_enabled else 5672)

        ssl_ctx = None
        if tls_enabled:
            # Create SSL context if TLS is enabled
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        # Establish connection to RabbitMQ using the configuration settings
        self.connection = await connect_robust(
            host=self.cfg.get("host", "localhost"),
            port=port,
            virtualhost=self.cfg.get("vhost", "/"),
            login=self.cfg.get("username", "guest"),
            password=self.cfg.get("password", "guest"),
            heartbeat=self.cfg.get("heartbeat", 600),
            ssl=tls_enabled,  # Enable SSL if needed
        )

        self.channel = await self.connection.channel()  # Create a new channel
        # Set prefetch count to avoid overwhelming the consumer
        await self.channel.set_qos(prefetch_count=1)

        # Declare RabbitMQ exchanges for different types of communication
        self.ex_bridge = await self.channel.declare_exchange(
            "ex.bridge.output", ExchangeType.TOPIC, durable=True
        )
        self.ex_result = await self.channel.declare_exchange(
            "ex.sim.result", ExchangeType.TOPIC, durable=True
        )
        self.ex_stream = await self.channel.declare_exchange(
            "ex.input.stream", ExchangeType.TOPIC, durable=True
        )

        # Declare the result queue where the agent will receive simulation
        # results
        self.queue = await self.channel.declare_queue(
            self.result_queue, durable=True
        )
        await self.queue.bind(
            self.ex_result,
            routing_key=f"{self.destination_id}.result.{self.agent_id}",
        )

    async def send_initial_interactive_request(
        self, payload: Dict[str, Any], request_id: str
    ) -> None:
        """
        Sends the initial request to the AnyLogic simulation. This includes necessary
        metadata and sets up the simulation environment.

        """
        payload["simulation"]["request_id"] = request_id
        payload["simulation"].setdefault("bridge_meta", {})[
            "protocol"] = "rabbitmq"

        routing_key = f"{self.agent_id}.{self.destination_id}"
        # Publish the request message to the bridge exchange
        await self.ex_bridge.publish(
            Message(
                body=yaml.dump(payload, default_flow_style=False).encode(),
                delivery_mode=DeliveryMode.PERSISTENT,  # Ensure message is persistent
                content_type="application/x-yaml",  # Content type is YAML
                message_id=str(uuid.uuid4()),  # Unique ID for the message
            ),
            routing_key=routing_key,
        )
        print(
            f"[INIT] Sent interactive request (rk='{routing_key}') request_id={request_id}")

    async def stream_inputs(self, stream_key: str) -> None:
        """
        Continuously sends input frames to AnyLogic simulation until completion.
        """
        # YOU WILL NEED TO ADJUST THIS FUNCTION TO ALIGN WITH THE SPECIFIC
        # STRUCTURE OF YOUR INPUT FRAMES. BELOW IS A SIMPLIFIED EXAMPLE.
        print(f"[INPUT STREAM] Publishing frames on '{stream_key}' …")
        k = 0
        while True:
            if self.stop_event.is_set():
                print("[INPUT STREAM] Received stop signal, ending input stream.")
                break

            # Example input frame structure; modify as needed
            if k % 7 == 0:
                state = "high"
            elif k % 5 == 0:
                state = "low"
            else:
                state = "medium"

            frame = {
                "type": "command to be executed",
                "data": {
                    "variable": "executionTime",
                    "state": state
                }
            }
            await self.ex_stream.publish(
                Message(
                    body=yaml.dump(frame).encode(),
                    content_type="application/x-yaml",
                    message_id=str(uuid.uuid4()),
                ),
                routing_key=stream_key,
            )

            k += 1
            await asyncio.sleep(1)

        print("[INPUT STREAM] Input loop finished.")

    async def handle_results(self) -> None:
        """
        Consumes results asynchronously from the AnyLogic simulation. When a result with status 'completed'
        is received, it stops the input stream.
        """
        async with self.queue.iterator() as q:
            async for msg in q:  # Continuously listen for incoming messages from the result queue
                async with msg.process():
                    result = yaml.safe_load(
                        msg.body)  # Parse the result message

                    print(f"\n[RESULT] {result}\n" + "-" * 40)

                    # Check if the simulation is completed
                    if isinstance(result, dict) and result.get(
                            "status") == "completed":
                        print("Received completion signal from AnyLogic.")
                        self.stop_event.set()  # Set the stop event to end the input stream
                        break


async def main() -> None:
    """
    Main entry point for the script. Handles the command-line arguments,
    loads configuration and payload, and starts the simulation.
    """
    # Command-line argument parsing
    parser = argparse.ArgumentParser(description="AnyLogic interactive client")
    parser.add_argument(
        "--config",
        "-c",
        default="use.yaml",
        help="YAML with RabbitMQ connection settings (default: use.yaml)",
    )
    parser.add_argument(
        "--api-payload",
        "-p",
        default="simulation.yaml",
        help="YAML simulation payload to send (default: simulation.yaml)",
    )
    args = parser.parse_args()

    # Load RabbitMQ configuration from the provided file
    async with await anyio.open_file(args.config, "r", encoding="utf-8") as f_cfg:
        rabbit_cfg = yaml.safe_load(await f_cfg.read()).get("rabbitmq", {})

    # Load the simulation payload from the provided file
    async with await anyio.open_file(args.api_payload, "r", encoding="utf-8") as f_pl:
        payload = yaml.safe_load(await f_pl.read())

    # Initialize the simulation client (here, it is AnyLogic-specific)
    client = InteractiveUsageAnylogicAgent("dt", "anylogic", rabbit_cfg)

    request_id = str(uuid.uuid4())  # Unique request ID for this simulation

    # Ensure the simulation type is 'interactive'
    simulation_type = payload["simulation"]["type"]
    if simulation_type != "interactive":
        raise ValueError(
            f"Simulation type must be 'interactive', got '{simulation_type}'")

    # Input stream source (RabbitMQ URL)
    stream_source = payload["simulation"]["inputs"]["stream_source"]
    # Extract the routing key for the stream
    stream_key = stream_source.replace("rabbitmq://", "")

    # Setup and send the initial interactive request to AnyLogic
    await client.setup()
    await client.send_initial_interactive_request(payload, request_id)

    # Run both result handler and input stream publisher concurrently
    await asyncio.gather(
        client.handle_results(),
        client.stream_inputs(request_id, stream_key),
    )

    print("Simulation client finished.")


if __name__ == "__main__":
    asyncio.run(main())
