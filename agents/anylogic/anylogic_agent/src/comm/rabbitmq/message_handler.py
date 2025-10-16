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

from .interfaces import IRabbitMQMessageHandler
from ...utils.logger import get_logger
from ...utils.create_response import create_response
from ...core.streaming import handle_streaming_simulation
from ...core.interactive import handle_interactive_simulation

logger = get_logger()


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

        source: str = method.routing_key.split('.')[0]

        try:
            msg_dict = self._parse_yaml_body(body, source, ch, method)
            if msg_dict is None:
                return

            validated_data = self._validate_message(
                msg_dict, source, ch, method)
            if validated_data is None:
                return

            self._process_simulation(
                validated_data, msg_dict, source, ch, method)

        except Exception as e:
            logger.error("Error processing message %s: %s", message_id, e)
            self._send_error_and_nack(source, ch, method, 'execution_error',
                                      'Error processing message', str(e))

    def _parse_yaml_body(
        self,
        body: bytes,
        source: str,
        ch: BlockingChannel,
        method: Basic.Deliver
    ) -> dict | None:
        """Parse YAML body and handle parsing errors."""
        try:
            msg_dict = yaml.safe_load(body)
            logger.debug("Parsed message: %s", msg_dict)
            return msg_dict
        except yaml.YAMLError as e:
            logger.error("YAML parsing error: %s", e)
            error_response = create_response(
                template_type='error',
                sim_file='',
                sim_type='',
                response_templates={},
                bridge_meta='unknown',
                request_id='unknown',
                error={'message': 'YAML parsing error',
                       'details': str(e), 'type': 'yaml_parse_error'}
            )
            self.rabbitmq_manager.send_result(source, error_response)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return None

    def _validate_message(
        self,
        msg_dict: dict,
        source: str,
        ch: BlockingChannel,
        method: Basic.Deliver
    ) -> dict | None:
        """Validate message structure and extract simulation data."""
        try:
            payload = MessagePayload(**msg_dict)
            logger.debug("Message validation successful")

            simulation_data = payload.simulation
            return {
                'sim_type': simulation_data.type,
                'sim_file': simulation_data.file,
                'bridge_meta': simulation_data.bridge_meta or 'unknown',
                'request_id': simulation_data.request_id
            }
        except Exception as e:
            logger.error("Message validation failed: %s", e)
            validated_data = self._extract_simulation_data_fallback(msg_dict)
            # Still return the data for error reporting
            return validated_data

    def _extract_simulation_data_fallback(self, msg_dict: dict) -> dict:
        """Extract simulation data from dict when validation fails."""
        defaults = {
            'sim_file': '',
            'sim_type': '',
            'bridge_meta': 'unknown',
            'request_id': 'unknown'
        }

        if isinstance(msg_dict, dict) and 'simulation' in msg_dict:
            sim_data = msg_dict['simulation']
            return {
                'sim_file': sim_data.get('file', ''),
                'sim_type': sim_data.get('type', ''),
                'bridge_meta': sim_data.get('bridge_meta', 'unknown'),
                'request_id': sim_data.get('request_id', 'unknown')
            }
        return defaults

    def _process_simulation(
        self,
        validated_data: dict,
        msg_dict: dict,
        source: str,
        ch: BlockingChannel,
        method: Basic.Deliver
    ) -> None:
        """Process simulation based on type."""
        sim_type = validated_data['sim_type']

        if sim_type == 'batch':
            # Batch simulations are handled the same way as streaming
            handle_streaming_simulation(
                msg_dict, source, self.rabbitmq_manager,
                self.config, self.response_templates
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
        elif sim_type == 'streaming':
            ch.basic_ack(delivery_tag=method.delivery_tag)
            handle_streaming_simulation(
                msg_dict, source, self.rabbitmq_manager,
                self.config, self.response_templates
            )
        elif sim_type == 'interactive':
            ch.basic_ack(delivery_tag=method.delivery_tag)
            handle_interactive_simulation(
                msg_dict, source, self.rabbitmq_manager,
                self.config, self.response_templates
            )
        else:
            self._handle_unknown_simulation_type(
                validated_data, source, ch, method)

    def _handle_unknown_simulation_type(
        self,
        validated_data: dict,
        source: str,
        ch: BlockingChannel,
        method: Basic.Deliver
    ) -> None:
        """Handle unknown simulation type error."""
        sim_type = validated_data['sim_type']
        logger.error("Unknown simulation type: %s", sim_type)

        error_response = create_response(
            template_type='error',
            sim_file=validated_data['sim_file'],
            sim_type=sim_type,
            response_templates={},
            bridge_meta=validated_data['bridge_meta'],
            request_id=validated_data['request_id'],
            error={
                'message': f'Unknown simulation type: {sim_type}',
                'type': 'invalid_simulation_type'
            }
        )
        self.rabbitmq_manager.send_result(source, error_response)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def _send_error_and_nack(
        self,
        source: str,
        ch: BlockingChannel,
        method: Basic.Deliver,
        error_type: str,
        error_message: str,
        error_details: str
    ) -> None:
        """Send error response and nack the message."""
        error_response = create_response(
            template_type='error',
            sim_file='',
            sim_type='',
            response_templates={},
            bridge_meta='unknown',
            request_id='unknown',
            error={
                'message': error_message,
                'details': error_details,
                'type': error_type
            }
        )
        try:
            self.rabbitmq_manager.send_result(source, error_response)
        except Exception as send_error:
            logger.error("Failed to send error response: %s", send_error)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
