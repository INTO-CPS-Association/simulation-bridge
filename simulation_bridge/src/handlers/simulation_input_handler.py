"""
Handler for incoming messages from Digital Twins to simulators.
"""
from typing import Any, Dict, List
import yaml
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties
from .base_handler import BaseMessageHandler
from ..utils.logger import get_logger

logger = get_logger()


class SimulationInputMessageHandler(BaseMessageHandler):
    """Handler for incoming messages from DTs to simulators"""

    def handle(
        self,
        ch: BlockingChannel,
        method: Basic.Deliver,
        properties: BasicProperties,
        body: bytes
    ) -> None:
        try:
            source: str = method.routing_key

            # Load the message body as YAML
            msg: Dict[str, Any] = yaml.safe_load(body)

            destinations: List[str] = msg.get('destinations', [])
            formatted_destinations = ", ".join(
                destinations) if destinations else "None"

            # Log the received message
            logger.debug(
                "Received input message from %s: %s",
                source,
                msg,
                extra={'message_id': properties.message_id}
            )
            logger.info(
                "Received simulation request from %s to %s",
                source,
                formatted_destinations,
                extra={'message_id': properties.message_id}
            )

            # Forward the message to all destinations
            for dest in msg.get('destinations', []):
                routing_key: str = f"{source}.{dest}"
                self.channel.basic_publish(
                    exchange='ex.bridge.output',
                    routing_key=routing_key,
                    body=body,  # Message body remains unchanged (in YAML)
                    properties=properties
                )
                logger.debug(
                    "Input message forwarded to %s",
                    routing_key,
                    extra={'message_id': properties.message_id}
                )

            # Acknowledge the message
            self.ack_message(ch, method.delivery_tag)
        except yaml.YAMLError as e:
            # Handle YAML errors
            logger.error(
                "YAML decoding error: %s",
                str(e),
                extra={'body': body, 'delivery_tag': method.delivery_tag}
            )
            self.nack_message(ch, method.delivery_tag)
        except Exception as e:
            # Handle generic errors
            logger.exception(
                "Error processing message: %s",
                str(e),
                extra={'delivery_tag': method.delivery_tag}
            )
            self.nack_message(ch, method.delivery_tag)
