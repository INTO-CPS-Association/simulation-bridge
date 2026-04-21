"""Message handler for processing incoming RabbitMQ messages."""

import uuid
from typing import Any, Dict, Optional

import yaml
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.batch import handle_batch_simulation
from ...utils.create_response import create_response
from ...utils.logger import get_logger
from .interfaces import IRabbitMQMessageHandler

logger = get_logger()


class SimulationInputs(BaseModel):
    """Model for simulation inputs - dynamic fields allowed."""

    model_config = ConfigDict(extra="allow")


class SimulationOutputs(BaseModel):
    """Model for simulation outputs - dynamic fields allowed."""

    model_config = ConfigDict(extra="allow")


class SimulationData(BaseModel):
    """Model for simulation data structure."""

    request_id: str
    client_id: str
    simulator: str
    type: str = Field(default="batch")
    file: str
    inputs: SimulationInputs
    outputs: Optional[SimulationOutputs] = None
    bridge_meta: Optional[Dict[str, Any]] = None

    @field_validator("type", mode="before")
    @classmethod
    def validate_sim_type(cls, value):
        """Only batch mode is supported by Python Agent."""
        if value != "batch":
            raise ValueError(f"Invalid simulation type: {value}. Must be 'batch'")
        return value


class MessagePayload(BaseModel):
    """Model for the entire message payload."""

    simulation: SimulationData
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class MessageHandler(IRabbitMQMessageHandler):
    """Handler for processing incoming messages from RabbitMQ."""

    def __init__(self, agent_id: str, rabbitmq_manager: Any, config: Optional[Dict]) -> None:
        self.agent_id = agent_id
        self.rabbitmq_manager = rabbitmq_manager
        self.config = config
        self.path_simulation = self.config.get("simulation", {}).get("path", None)
        self.response_templates = self.config.get("response_templates", {})

    def get_agent_id(self) -> str:
        return self.agent_id

    def handle_message(
        self,
        ch: BlockingChannel,
        method: Basic.Deliver,
        properties: BasicProperties,
        body: bytes,
    ) -> None:
        message_id = properties.message_id if properties.message_id else "unknown"
        source = method.routing_key.split(".")[0]

        try:
            msg_dict = yaml.safe_load(body)
            payload = MessagePayload(**msg_dict)
            sim_data = payload.simulation

            handle_batch_simulation(
                msg_dict,
                source,
                self.rabbitmq_manager,
                self.path_simulation,
                self.response_templates,
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info("Handled batch request %s for file %s", sim_data.request_id, sim_data.file)

        except Exception as error:  # pylint: disable=broad-except
            logger.error("Error processing message %s: %s", message_id, error)
            error_response = create_response(
                template_type="error",
                sim_file="",
                sim_type="batch",
                response_templates={},
                bridge_meta="unknown",
                request_id="unknown",
                error={
                    "message": "Error processing message",
                    "details": str(error),
                    "type": "execution_error",
                },
            )
            try:
                self.rabbitmq_manager.send_result(source, error_response)
            except Exception as send_error:  # pylint: disable=broad-except
                logger.error("Failed to send error response: %s", send_error)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
