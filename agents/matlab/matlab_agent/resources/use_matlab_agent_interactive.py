"""
use_matlab_agent_interactive_async.py

Asynchronous RabbitMQ client for sending interactive simulation requests
to MATLAB
"""

# pylint: disable=missing-module-docstring, missing-class-docstring,
# missing-function-docstring, too-many-instance-attributes,
# attribute-defined-outside-init

import asyncio
import argparse
import uuid
from typing import Any, Dict
import anyio
import yaml
from aio_pika import (
    connect_robust,
    Message,
    DeliveryMode,
    ExchangeType,
)


class AsyncInteractiveMatlabClient:
    """Asynchronous client for sending interactive simulation requests to MATLAB."""

    def __init__(self, agent_id: str, destination_id: str,
                 config: Dict[str, Any]):
        self.agent_id = agent_id
        self.destination_id = destination_id
        self.config = config
        self.result_queue = f"Q.{agent_id}.matlab.result"

    async def setup(self):
        """Setup RabbitMQ connection, exchanges, and queues."""
        rabbit_cfg = self.config.get("rabbitmq", {})
        self.connection = await connect_robust(
            host=rabbit_cfg.get("host", "localhost"),
            port=rabbit_cfg.get("port", 5672),
            virtualhost=rabbit_cfg.get("vhost", "/"),
            login=rabbit_cfg.get("username", "guest"),
            password=rabbit_cfg.get("password", "guest"),
        )
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=1)
        self.ex_bridge = await self.channel.declare_exchange(
            "ex.bridge.output", ExchangeType.TOPIC, durable=True
        )
        self.ex_result = await self.channel.declare_exchange(
            "ex.sim.result", ExchangeType.TOPIC, durable=True
        )
        self.ex_stream = await self.channel.declare_exchange(
            "ex.input.stream", ExchangeType.TOPIC, durable=True
        )

        self.queue = await self.channel.declare_queue(self.result_queue, durable=True)
        await self.queue.bind(
            self.ex_result, routing_key=f"{
                self.destination_id}.result.{
                self.agent_id}"
        )

    async def send_initial_interactive_request(
        self, payload: Dict[str, Any], request_id: str
    ):
        """Send the initial interactive simulation request to MATLAB."""
        payload["simulation"]["request_id"] = request_id
        payload["simulation"].setdefault("bridge_meta", {})[
            "protocol"] = "rabbitmq"

        yaml_body = yaml.dump(payload, default_flow_style=False)
        routing_key = f"{self.agent_id}.{self.destination_id}"
        await self.ex_bridge.publish(
            Message(
                body=yaml_body.encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/x-yaml",
                message_id=str(uuid.uuid4()),
            ),
            routing_key=routing_key,
        )
        print(f"[INIT] Simulation request sent with request_id: {request_id}")

    async def stream_inputs(self, request_id: str, stream_key: str):
        """Stream input frames to MATLAB for the interactive simulation."""
        print(f"[INPUT STREAM] Sending input frames to {stream_key}...")
        for k in range(100):
            t = k * 0.1
            vx = 1.0
            vy = 0.5
            x = vx * t
            y = vy * t
            frame = {
                "simulation": {
                    "request_id": request_id,
                    "inputs": {"t": t, "x": x, "y": y, "vx": vx, "vy": vy},
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
            await asyncio.sleep(0.1)

    async def handle_results(self):
        """Handle incoming results from MATLAB and print them."""
        async with self.queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    result = yaml.safe_load(message.body)
                    print(f"\n[RESULT] Received: {result}")
                    print("-" * 40)


async def main():
    """Main entry point for the asynchronous MATLAB agent client."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-payload",
        type=str,
        default="../api/simulation.yaml",
    )
    args = parser.parse_args()

    async with await anyio.open_file(args.api_payload, "r", encoding="utf-8") as f:
        payload = yaml.safe_load(await f.read())

    config = payload.get("config", {})
    client = AsyncInteractiveMatlabClient("dt", "matlab", config)

    request_id = str(uuid.uuid4())
    stream_source = payload["simulation"]["inputs"]["stream_source"]
    stream_key = stream_source.replace("rabbitmq://", "")

    await client.setup()
    await client.send_initial_interactive_request(payload, request_id)

    # Start listener and streaming concurrently
    await asyncio.gather(
        client.handle_results(),
        client.stream_inputs(request_id, stream_key),
    )


if __name__ == "__main__":
    asyncio.run(main())
