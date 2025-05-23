"""
Message handler for processing incoming RabbitMQ messages.
"""
import uuid
from typing import Any, Optional, Dict

import yaml
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .interfaces import IRabbitMQMessageHandler
from ...utils.logger import get_logger
from ...utils.create_response import create_response
from ...core.batch import handle_batch_simulation
from ...core.streaming import handle_streaming_simulation

logger = get_logger()


class SimulationInputs(BaseModel):
    """Model for simulation inputs - dynamic fields allowed"""
    model_config = ConfigDict(extra="allow")


class SimulationOutputs(BaseModel):
    """Model for simulation outputs - dynamic fields allowed"""
    model_config = ConfigDict(extra="allow")


class SimulationData(BaseModel):
    """Model for simulation data structure"""
    id: str
    destination: str
    type: str = Field(default="batch")
    file: str
    inputs: 'SimulationInputs'
    outputs: Optional['SimulationOutputs'] = None
    bridge_meta: Optional[Dict[str, Any]] = None

    @field_validator('type', mode='before')
    @classmethod
    def validate_sim_type(cls, v):
        """Validate that simulation type is either 'batch' or 'streaming'"""
        if v not in ['batch', 'streaming']:
            raise ValueError(
                f"Invalid simulation type: {v}. Must be 'batch' or 'streaming'")
        return v


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

        # Extract the message source
        source: str = method.routing_key.split('.')[0]

        try:
            # Load the message body as YAML
            try:
                # Initialize msg_dict to avoid reference issues in case of
                # parsing error
                msg_dict = {}
                msg_dict = yaml.safe_load(body)
                logger.debug("Parsed message: %s", msg_dict)
            except yaml.YAMLError as e:
                logger.error("YAML parsing error: %s", e)
                error_response = create_response(
                    template_type='error',
                    sim_file=msg_dict.get('simulation', {}).get(
                        'file', '') if isinstance(msg_dict, dict) else '',
                    sim_type=msg_dict.get('simulation', {}).get(
                        'type', '') if isinstance(msg_dict, dict) else '',
                    response_templates={},
                    bridge_meta=msg_dict.get('simulation', {}).get(
                        'bridge_meta', 'unknown') if isinstance(msg_dict, dict) 
                    else 'unknown',
                    error={'message': 'YAML parsing error',
                           'details': str(e), 'type': 'yaml_parse_error'}
                )
                self.rabbitmq_manager.send_result(source, error_response)
                ch.basic_nack(delivery_tag=method.delivery_tag,
                              requeue=False)  # Don't requeue the message
                return

            # Validate the message structure using Pydantic
            try:
                # Validate the message against our expected schema
                payload = MessagePayload(**msg_dict)
                logger.debug("Message validation successful")

                # Access the validated data
                simulation_data = payload.simulation
                sim_type = simulation_data.type
                sim_file = simulation_data.file
                bridge_meta = msg_dict.get('simulation', {}).get(
                    'bridge_meta', 'unknown') if isinstance(msg_dict, dict) else 'unknown'


            except Exception as e:  # pylint: disable=broad-except
                logger.error("Message validation failed: %s", e)

                # Create an error response
                error_response = create_response(
                    template_type='error',
                    sim_file=msg_dict.get('simulation', {}).get(
                        'file', '') if isinstance(msg_dict, dict) else '',
                    sim_type=msg_dict.get('simulation', {}).get(
                        'type', '') if isinstance(msg_dict, dict) else '',
                    response_templates={},
                    bridge_meta = bridge_meta,
                    error={
                        'message': 'Message validation failed',
                        'details': str(e),
                        'type': 'validation_error'
                    }
                    
                )
                # Send the error response back to the source
                self.rabbitmq_manager.send_result(source, error_response)

                # Acknowledge the message so it's not requeued
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

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
            else:
                # This shouldn't happen due to Pydantic validation, but just in
                # case
                logger.error("Unknown simulation type: %s", sim_type)
                error_response = create_response(
                    template_type='error',
                    sim_file=sim_file,
                    sim_type=sim_type,
                    response_templates={},
                    error={
                        'message': f'Unknown simulation type: {sim_type}',
                        'type': 'invalid_simulation_type'
                    }
                )
                self.rabbitmq_manager.send_result(source, error_response)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error processing message %s: %s", message_id, e)
            error_response = create_response(
                template_type='error',
                sim_file='',
                sim_type='',
                response_templates={},
                bridge_meta='unknown',
                error={
                    'message': 'Error processing message',
                    'details': str(e),
                    'type': 'execution_error'
                }
            )
            # Try to send the error response back
            try:
                self.rabbitmq_manager.send_result(source, error_response)
            except Exception as send_error:  # pylint: disable=broad-except
                logger.error("Failed to send error response: %s", send_error)

            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
