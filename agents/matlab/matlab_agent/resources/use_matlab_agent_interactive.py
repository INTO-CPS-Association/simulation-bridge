"""
use_matlab_agent_interactive.py

Asynchronous RabbitMQ client for sending interactive simulation requests
to a MATLAB agent, with optional TLS and separate config/payload files.
"""

# pylint: disable=missing-module-docstring, missing-class-docstring,
# missing-function-docstring, too-many-instance-attributes,
# attribute-defined-outside-init

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


class InteractiveUsageMatlabAgent:
    """Asynchronous client for sending interactive simulation requests."""

    def __init__(self, agent_id: str, destination_id: str,
                 rabbitmq_cfg: Dict[str, Any]) -> None:
        self.agent_id = agent_id
        self.destination_id = destination_id
        self.cfg = rabbitmq_cfg
        self.result_queue = f"Q.{agent_id}.matlab.result"

    async def setup(self) -> None:
        """Connect to RabbitMQ, declare exchanges/queues."""
        tls_enabled: bool = bool(self.cfg.get("tls", False))
        port = self.cfg.get("port", 5671 if tls_enabled else 5672)

        ssl_ctx = None
        if tls_enabled:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        self.connection = await connect_robust(
            host=self.cfg.get("host", "localhost"),
            port=port,
            virtualhost=self.cfg.get("vhost", "/"),
            login=self.cfg.get("username", "guest"),
            password=self.cfg.get("password", "guest"),
            heartbeat=self.cfg.get("heartbeat", 600),
            ssl=tls_enabled,
        )

        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=1)

        # Exchanges
        self.ex_bridge = await self.channel.declare_exchange(
            "ex.bridge.output", ExchangeType.TOPIC, durable=True
        )
        self.ex_result = await self.channel.declare_exchange(
            "ex.sim.result", ExchangeType.TOPIC, durable=True
        )
        self.ex_stream = await self.channel.declare_exchange(
            "ex.input.stream", ExchangeType.TOPIC, durable=True
        )

        # Result queue/binding
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
        """Publish the first message that kicks off the interactive sim."""
        payload["simulation"]["request_id"] = request_id
        payload["simulation"].setdefault("bridge_meta", {})["protocol"] = "rabbitmq"

        routing_key = f"{self.agent_id}.{self.destination_id}"
        await self.ex_bridge.publish(
            Message(
                body=yaml.dump(payload, default_flow_style=False).encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/x-yaml",
                message_id=str(uuid.uuid4()),
            ),
            routing_key=routing_key,
        )
        print(f"[INIT] Sent interactive request (rk='{routing_key}') "
              f"request_id={request_id}")

    async def stream_inputs(self, request_id: str, stream_key: str) -> None:
        """Continuously send input frames to MATLAB."""
        print(f"[INPUT STREAM] Publishing frames on '{stream_key}' …")
        for k in range(10000):
            t = k * 0.1
            vx, vy = 1.0, 0.5
            frame = {
                "simulation": {
                    "request_id": request_id,
                    "inputs": {"t": t, "x": vx*t, "y": vy*t, "vx": vx, "vy": vy},
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

    async def handle_results(self) -> None:
        """Consume results asynchronously and print them."""
        async with self.queue.iterator() as q:
            async for msg in q:
                async with msg.process():
                    result = yaml.safe_load(msg.body)
                    print(f"\n[RESULT] {result}\n" + "-"*40)


async def main() -> None:
    parser = argparse.ArgumentParser(description="MATLAB interactive client")
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

    # --- Load config & payload
    async with await anyio.open_file(args.config, "r", encoding="utf-8") as f_cfg:
        rabbit_cfg = yaml.safe_load(await f_cfg.read()).get("rabbitmq", {})

    async with await anyio.open_file(args.api_payload, "r", encoding="utf-8") as f_pl:
        payload = yaml.safe_load(await f_pl.read())

    # --- Client
    client = InteractiveUsageMatlabAgent("dt", "matlab", rabbit_cfg)

    request_id = str(uuid.uuid4())
    stream_source = payload["simulation"]["inputs"]["stream_source"]
    stream_key = stream_source.replace("rabbitmq://", "")

    await client.setup()
    await client.send_initial_interactive_request(payload, request_id)

    # run listener & streamer concurrently
    await asyncio.gather(
        client.handle_results(),
        client.stream_inputs(request_id, stream_key),
    )


if __name__ == "__main__":
    asyncio.run(main())
