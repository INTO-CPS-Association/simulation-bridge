"""Simple client helper to publish a batch request to Python Agent."""

import json
import pika


REQUEST = {
    "simulation": {
        "request_id": "req-001",
        "client_id": "client-001",
        "simulator": "python",
        "type": "batch",
        "file": "example_cli_program.py",
        "inputs": {
            "first": 5,
            "second": 7
        },
        "outputs": ["sum"]
    }
}


def main() -> None:
    connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
    channel = connection.channel()
    channel.exchange_declare(exchange="ex.bridge.output", exchange_type="topic", durable=True)
    channel.basic_publish(
        exchange="ex.bridge.output",
        routing_key="demo.python",
        body=json.dumps(REQUEST).encode("utf-8"),
    )
    connection.close()


if __name__ == "__main__":
    main()
