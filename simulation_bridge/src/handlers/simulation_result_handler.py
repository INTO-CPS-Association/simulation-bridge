"""
Handler for result messages from simulators to Digital Twins.
"""
from typing import Any, Dict
import yaml
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties
from .base_handler import BaseMessageHandler
from ..utils.logger import get_logger

logger = get_logger()


class SimulationResultMessageHandler(BaseMessageHandler):
    """Handler for result messages from simulators to DTs"""

    def handle(
        self,
        ch: BlockingChannel,
        method: Basic.Deliver,
        properties: BasicProperties,
        body: bytes
    ) -> None:
        try:
            # The routing key will be in the format:
            # sim<ID>.result.<destination>
            parts: list[str] = method.routing_key.split('.')
            if len(parts) < 3:
                logger.error(
                    "Invalid routing key format for result message: %s",
                    method.routing_key,
                    extra={'delivery_tag': method.delivery_tag}
                )
                self.nack_message(ch, method.delivery_tag)
                return

            source: str = parts[0]  # simulator
            destination: str = parts[2]  # recipient (dt, pt, etc)

            # Load the message body as YAML
            msg: Dict[str, Any] = yaml.safe_load(body)

            status = msg.get('status', '')
            if status == 'completed':
                logger.info("Simulation completed correctly")
            if status == 'error':
                # Retrieve error details from the message and log it
                error = msg.get('error', {})
                error_code = error.get('code', 'Unknown')
                error_message = error.get(
                    'message', 'No error message provided.')
                error_type = error.get('type', 'Unknown')
                logger.error(
                    "Simulation failed with error (Code: %s, Type: %s): %s",
                    error_code,
                    error_type,
                    error_message,
                    extra={'message_id': properties.message_id}
                )
            # Log the received message
            logger.debug(
                "Received result message from %s to %s: %s",
                source,
                destination,
                msg,
                extra={'message_id': properties.message_id}
            )

            # Forward the message to the recipient
            routing_key: str = f"{source}.result"
            self.channel.basic_publish(
                exchange='ex.bridge.result',
                routing_key=routing_key,
                body=body,  # Message body remains unchanged (in YAML)
                properties=properties
            )
            logger.debug(
                "Result message forwarded to %s via %s",
                destination,
                routing_key,
                extra={'message_id': properties.message_id}
            )

            # Acknowledge the message
            self.ack_message(ch, method.delivery_tag)
        except yaml.YAMLError as e:
            # Handle YAML errors
            logger.error(
                "YAML decoding error in result message: %s",
                str(e),
                extra={'body': body, 'delivery_tag': method.delivery_tag}
            )
            self.nack_message(ch, method.delivery_tag)
        except Exception as e:
            # Handle generic errors
            logger.exception(
                "Error processing result message: %s",
                str(e),
                extra={'delivery_tag': method.delivery_tag}
            )
            self.nack_message(ch, method.delivery_tag)
