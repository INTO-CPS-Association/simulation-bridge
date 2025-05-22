"""
Handler for incoming messages from Digital Twins to simulators.
"""
from typing import Any, Dict, List
import yaml
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties
from .base_handler import BaseMessageHandler
from ...utils.logger import get_logger

logger = get_logger()


class SimulationInputMessageHandler(BaseMessageHandler):
    def handle(self, ch, method, properties, body: bytes) -> None:
        try:
            source = method.routing_key
            # YAML decoding
            msg = yaml.safe_load(body)
            logger.debug(
                "Raw message body (str): %s",
                body.decode('utf-8', errors='replace'),
                extra={'message_id': properties.message_id}
            )
            # VALIDATION: must be a dict
            if not isinstance(msg, dict):
                logger.error(
                    "Invalid message format, expected dict but got %s",
                    type(msg).__name__,
                    extra={'body': body, 'delivery_tag': method.delivery_tag}
                )
                self.ack_message(ch, method.delivery_tag)
                return

            destinations = msg.get('destinations', [])
            formatted_destinations = ", ".join(destinations) or "None"

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

            for dest in destinations:
                routing_key = f"{source}.{dest}"
                self.channel.basic_publish(
                    exchange='ex.bridge.output',
                    routing_key=routing_key,
                    body=body,
                    properties=properties
                )
                logger.debug(
                    "Input message forwarded to %s",
                    routing_key,
                    extra={'message_id': properties.message_id}
                )

            self.ack_message(ch, method.delivery_tag)

        except yaml.YAMLError as e:
            logger.error(
                "YAML decoding error: %s",
                str(e),
                extra={'body': body, 'delivery_tag': method.delivery_tag}
            )
            self.nack_message(ch, method.delivery_tag)

        except Exception as e:
            logger.exception(
                "Error processing message: %s",
                str(e),
                extra={'delivery_tag': method.delivery_tag}
            )
            self.nack_message(ch, method.delivery_tag)
