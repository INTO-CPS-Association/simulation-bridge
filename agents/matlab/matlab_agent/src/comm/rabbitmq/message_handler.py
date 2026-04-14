"""
Message handler for processing incoming RabbitMQ messages.
"""
import uuid
from typing import Any, Optional, Dict

import yaml
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties
from pydantic import (
    BaseModel, ConfigDict, Field, field_validator, model_validator
)
import queue

from base_agent.comm.rabbitmq.interfaces import IRabbitMQMessageHandler
from base_agent.comm.rabbitmq.message_processing import (
    SimulationMessageContext,
    build_error_response,
    extract_context_from_message,
    extract_source_from_routing_key,
    parse_message_body,
    validate_message_payload,
)
from base_agent.utils.create_response import create_response
from base_agent.utils.logger import get_logger
from ...core.batch import handle_batch_simulation
from ...core.streaming import handle_streaming_simulation
from ...core.interactive import handle_interactive_simulation

logger = get_logger("MATLAB-AGENT")


class SimulationInputs(BaseModel):
    """Model for simulation inputs - dynamic fields allowed"""
    stream_source: str | None = None
    model_config = ConfigDict(extra="allow")


class SimulationOutputs(BaseModel):
    """Model for simulation outputs - dynamic fields allowed"""
    model_config = ConfigDict(extra="allow")


class SimulationData(BaseModel):
    """Model for simulation data structure"""
    request_id: str
    client_id: str
    simulator: str
    type: str = Field(default="batch")
    file: str
    inputs: 'SimulationInputs'
    outputs: Optional['SimulationOutputs'] = None
    bridge_meta: Optional[Dict[str, Any]] = None

    @field_validator('type', mode='before')
    @classmethod
    def validate_sim_type(cls, v):
        if v not in {'batch', 'streaming', 'interactive'}:
            raise ValueError(
                f"Invalid simulation type: {v}. "
                "Must be 'batch', 'streaming' or 'interactive'"
            )
        return v

    @model_validator(mode='after')
    def check_stream_source_for_interactive(self):
        """
        Validate that 'inputs.stream_source' is provided
        for interactive simulations.
        """
        if self.type == 'interactive' and not self.inputs.stream_source:
            raise ValueError(
                "For 'interactive' simulations you must provide "
                "'inputs.stream_source'"
            )
        return self


class MessagePayload(BaseModel):
    """Model for the entire message payload"""
    simulation: SimulationData
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class MessageHandler(IRabbitMQMessageHandler):
    """
    Handler for processing incoming messages from RabbitMQ.
    Implements the IRabbitMQMessageHandler interface.
    """

    def __init__(self, agent_id: str, rabbitmq_manager: Any,
                 config: Optional[Dict]) -> None:
        """
        Initialize the message handler.

        Args:
            agent_id (str): The ID of the agent
            rabbitmq_manager (RabbitMQManager): The RabbitMQ manager instance
        """
        self.agent_id = agent_id
        self.rabbitmq_manager = rabbitmq_manager
        self.config = config
        self.path_simulation = self.config.get(
            'simulation', {}).get(
            'path', None)
        self.response_templates = self.config.get(
            'response_templates', {})
        self.interactive_queues: Dict[str, queue.Queue] = {}

    def get_agent_id(self) -> str:
        """
        Retrieve the agent ID.

        Returns:
            str: The ID of the agent
        """
        return self.agent_id

    def _send_error_to_source(
        self,
        source: str,
        context: SimulationMessageContext,
        error_payload: Dict[str, Any],
    ) -> None:
        """Build and send an error response to the source queue."""
        error_response = build_error_response(
            response_builder=create_response,
            context=context,
            error=error_payload,
        )
        self.rabbitmq_manager.send_result(source, error_response)

    def _send_error_and_nack(
        self,
        ch: BlockingChannel,
        method: Basic.Deliver,
        source: str,
        context: SimulationMessageContext,
        error_payload: Dict[str, Any],
    ) -> None:
        """Send an error response and reject the message without requeue."""
        self._send_error_to_source(source, context, error_payload)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def handle_message(
        self,
        ch: BlockingChannel,
        method: Basic.Deliver,
        properties: BasicProperties,
        body: bytes
    ) -> None:
        """
        Process incoming messages from RabbitMQ with Pydantic validation.

        Args:
            ch (BlockingChannel): Channel object
            method (Basic.Deliver): Delivery method
            properties (BasicProperties): Message properties
            body (bytes): Message body
        """
        message_id = properties.message_id if properties.message_id else "unknown"
        logger.debug("Received message %s", message_id)
        logger.debug("Message routing key: %s", method.routing_key)

        # Extract the message source
        source: str = extract_source_from_routing_key(method.routing_key)
        msg_dict: Any = {}

        try:
            # Load the message body as YAML
            try:
                msg_dict = parse_message_body(body, yaml.safe_load, logger)
            except yaml.YAMLError as parsing_error:
                logger.error("YAML parsing error: %s", parsing_error)
                self._send_error_and_nack(
                    ch=ch,
                    method=method,
                    source=source,
                    context=extract_context_from_message(msg_dict),
                    error_payload={
                        'message': 'YAML parsing error',
                        'details': str(parsing_error),
                        'type': 'yaml_parse_error'
                    },
                )
                return
            # Validate the message structure using Pydantic
            _, message_context, validation_error = validate_message_payload(
                msg_dict=msg_dict,
                payload_factory=lambda payload_data: MessagePayload(**payload_data),
                logger=logger,
            )
            if validation_error:
                self._send_error_and_nack(
                    ch=ch,
                    method=method,
                    source=source,
                    context=message_context,
                    error_payload={
                        'message': 'Message validation failed',
                        'details': validation_error,
                        'type': 'validation_error'
                    },
                )
                return

            sim_type = message_context.sim_type
            logger.info("Received simulation type: %s", sim_type)
            # Process based on simulation type
            if sim_type == 'batch':
                handle_batch_simulation(
                    msg_dict,
                    source,
                    self.rabbitmq_manager,
                    self.path_simulation,
                    self.response_templates)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            elif sim_type == 'streaming':
                ch.basic_ack(delivery_tag=method.delivery_tag)
                tcp_settings = self.config.get(
                    'tcp', {})
                handle_streaming_simulation(
                    msg_dict, source,
                    self.rabbitmq_manager,
                    self.path_simulation,
                    self.response_templates,
                    tcp_settings
                )
            elif sim_type == 'interactive':
                ch.basic_ack(delivery_tag=method.delivery_tag)
                tcp_settings = self.config.get('tcp', {})
                handle_interactive_simulation(
                    msg_dict, source,
                    self.rabbitmq_manager,
                    self.path_simulation,
                    self.response_templates,
                    tcp_settings
                )
            else:
                logger.error("Unknown simulation type: %s", sim_type)
                self._send_error_and_nack(
                    ch=ch,
                    method=method,
                    source=source,
                    context=message_context,
                    error_payload={
                        'message': f'Unknown simulation type: {sim_type}',
                        'type': 'invalid_simulation_type'
                    }
                )

        except Exception as processing_error:
            logger.error("Error processing message %s: %s", message_id, processing_error)
            error_response = build_error_response(
                response_builder=create_response,
                context=SimulationMessageContext(),
                error={
                    'message': 'Error processing message',
                    'details': str(processing_error),
                    'type': 'execution_error'
                }
            )
            try:
                self.rabbitmq_manager.send_result(source, error_response)
            except Exception as send_error:  # pylint: disable=broad-except
                logger.error("Failed to send error response: %s", send_error)

            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
