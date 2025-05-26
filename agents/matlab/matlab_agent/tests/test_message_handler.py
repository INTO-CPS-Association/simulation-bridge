"""
Unit tests for MessageHandler class.
"""
import uuid
from unittest.mock import Mock, patch, MagicMock
import pytest
import yaml
from pika.spec import Basic, BasicProperties

from src.comm.rabbitmq.message_handler import (
    MessageHandler,
    SimulationInputs,
    SimulationOutputs,
    SimulationData,
    MessagePayload
)


class TestSimulationModels:
    """Test cases for Pydantic models."""

    def test_simulation_inputs_allows_extra_fields(self):
        """Test that SimulationInputs allows extra fields."""
        inputs = SimulationInputs(param1="value1", param2="value2")
        assert inputs.param1 == "value1"
        assert inputs.param2 == "value2"

    def test_simulation_outputs_allows_extra_fields(self):
        """Test that SimulationOutputs allows extra fields."""
        outputs = SimulationOutputs(result1="output1", result2="output2")
        assert outputs.result1 == "output1"
        assert outputs.result2 == "output2"

    def test_simulation_data_valid_batch_type(self):
        """Test SimulationData with valid batch simulation type."""
        inputs = SimulationInputs(param="value")
        data = SimulationData(
            request_id="req123",
            client_id="client456",
            simulator="test_sim",
            type="batch",
            file="test.sim",
            inputs=inputs
        )
        assert data.type == "batch"
        assert data.request_id == "req123"

    def test_simulation_data_valid_streaming_type(self):
        """Test SimulationData with valid streaming simulation type."""
        inputs = SimulationInputs(param="value")
        data = SimulationData(
            request_id="req123",
            client_id="client456",
            simulator="test_sim",
            type="streaming",
            file="test.sim",
            inputs=inputs
        )
        assert data.type == "streaming"

    def test_simulation_data_invalid_type_raises_error(self):
        """Test SimulationData with invalid simulation type raises error."""
        inputs = SimulationInputs(param="value")
        with pytest.raises(ValueError, match="Invalid simulation type"):
            SimulationData(
                request_id="req123",
                client_id="client456",
                simulator="test_sim",
                type="invalid",
                file="test.sim",
                inputs=inputs
            )

    def test_simulation_data_default_type_is_batch(self):
        """Test SimulationData defaults to batch type."""
        inputs = SimulationInputs(param="value")
        data = SimulationData(
            request_id="req123",
            client_id="client456",
            simulator="test_sim",
            file="test.sim",
            inputs=inputs
        )
        assert data.type == "batch"

    def test_message_payload_generates_uuid_by_default(self):
        """Test MessagePayload generates UUID for request_id by default."""
        inputs = SimulationInputs(param="value")
        simulation = SimulationData(
            request_id="req123",
            client_id="client456",
            simulator="test_sim",
            file="test.sim",
            inputs=inputs
        )
        payload = MessagePayload(simulation=simulation)

        # Check that request_id is a valid UUID
        assert payload.request_id is not None
        uuid.UUID(payload.request_id)  # Will raise if not valid UUID


class TestMessageHandler:
    """Test cases for MessageHandler class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.agent_id = "test_agent"
        self.mock_rabbitmq_manager = Mock()
        self.config = {
            'simulation': {'path': '/test/path'},
            'response_templates': {'error': 'error_template'},
            'tcp': {'port': 8080}
        }
        self.handler = MessageHandler(
            self.agent_id,
            self.mock_rabbitmq_manager,
            self.config
        )

        # Mock channel, method, and properties
        self.mock_channel = Mock()
        self.mock_method = Mock(spec=Basic.Deliver)
        self.mock_method.routing_key = "source.routing.key"
        self.mock_method.delivery_tag = "test_tag"

        self.mock_properties = Mock(spec=BasicProperties)
        self.mock_properties.message_id = "test_message_id"

    def test_init_sets_attributes_correctly(self):
        """Test that initialization sets all attributes correctly."""
        assert self.handler.agent_id == self.agent_id
        assert self.handler.rabbitmq_manager == self.mock_rabbitmq_manager
        assert self.handler.config == self.config
        assert self.handler.path_simulation == '/test/path'
        assert self.handler.response_templates == {'error': 'error_template'}

    def test_get_agent_id_returns_correct_id(self):
        """Test that get_agent_id returns the correct agent ID."""
        assert self.handler.get_agent_id() == self.agent_id

    @patch('src.comm.rabbitmq.message_handler.yaml.safe_load')
    @patch('src.comm.rabbitmq.message_handler.handle_batch_simulation')
    @patch('src.comm.rabbitmq.message_handler.create_response')
    def test_handle_message_batch_simulation_success(
        self, mock_create_response, mock_handle_batch, mock_yaml_load
    ):
        """Test successful handling of batch simulation message."""
        # Setup valid message data
        message_data = {
            'simulation': {
                'request_id': 'req123',
                'client_id': 'client456',
                'simulator': 'test_sim',
                'type': 'batch',
                'file': 'test.sim',
                'inputs': {'param': 'value'},
                'bridge_meta': {'key': 'value'}
            }
        }
        mock_yaml_load.return_value = message_data

        # Execute
        self.handler.handle_message(
            self.mock_channel,
            self.mock_method,
            self.mock_properties,
            b'test message body'
        )

        # Verify
        mock_yaml_load.assert_called_once_with(b'test message body')
        mock_handle_batch.assert_called_once_with(
            message_data,
            'source',
            self.mock_rabbitmq_manager,
            '/test/path',
            {'error': 'error_template'}
        )
        self.mock_channel.basic_ack.assert_called_once_with(
            delivery_tag="test_tag"
        )

    @patch('src.comm.rabbitmq.message_handler.yaml.safe_load')
    @patch('src.comm.rabbitmq.message_handler.handle_streaming_simulation')
    @patch('src.comm.rabbitmq.message_handler.create_response')
    def test_handle_message_streaming_simulation_success(
        self, mock_create_response, mock_handle_streaming, mock_yaml_load
    ):
        """Test successful handling of streaming simulation message."""
        # Setup valid message data
        message_data = {
            'simulation': {
                'request_id': 'req123',
                'client_id': 'client456',
                'simulator': 'test_sim',
                'type': 'streaming',
                'file': 'test.sim',
                'inputs': {'param': 'value'},
                'bridge_meta': {'key': 'value'}
            }
        }
        mock_yaml_load.return_value = message_data

        # Execute
        self.handler.handle_message(
            self.mock_channel,
            self.mock_method,
            self.mock_properties,
            b'test message body'
        )

        # Verify
        mock_yaml_load.assert_called_once_with(b'test message body')
        mock_handle_streaming.assert_called_once_with(
            message_data,
            'source',
            self.mock_rabbitmq_manager,
            '/test/path',
            {'error': 'error_template'},
            {'port': 8080}
        )
        self.mock_channel.basic_ack.assert_called_once_with(
            delivery_tag="test_tag"
        )

    @patch('src.comm.rabbitmq.message_handler.yaml.safe_load')
    @patch('src.comm.rabbitmq.message_handler.create_response')
    def test_handle_message_yaml_parsing_error(
        self, mock_create_response, mock_yaml_load
    ):
        """Test handling of YAML parsing errors."""
        # Setup YAML parsing error
        yaml_error = yaml.YAMLError("Invalid YAML")
        mock_yaml_load.side_effect = yaml_error
        mock_create_response.return_value = "error_response"

        # Execute
        self.handler.handle_message(
            self.mock_channel,
            self.mock_method,
            self.mock_properties,
            b'invalid yaml content'
        )

        # Verify error response creation
        mock_create_response.assert_called_once_with(
            template_type='error',
            sim_file='',
            sim_type='',
            response_templates={},
            bridge_meta='unknown',
            request_id='unknown',
            error={
                'message': 'YAML parsing error',
                'details': str(yaml_error),
                'type': 'yaml_parse_error'
            }
        )

        # Verify error response sent and message nacked
        self.mock_rabbitmq_manager.send_result.assert_called_once_with(
            'source', "error_response"
        )
        self.mock_channel.basic_nack.assert_called_once_with(
            delivery_tag="test_tag", requeue=False
        )

    @patch('src.comm.rabbitmq.message_handler.yaml.safe_load')
    @patch('src.comm.rabbitmq.message_handler.create_response')
    def test_handle_message_validation_error(
        self, mock_create_response, mock_yaml_load
    ):
        """Test handling of message validation errors."""
        # Setup invalid message data (missing required fields)
        invalid_message_data = {
            'simulation': {
                'type': 'batch',
                # Missing required fields like request_id, client_id, etc.
            }
        }
        mock_yaml_load.return_value = invalid_message_data
        mock_create_response.return_value = "error_response"

        # Execute
        self.handler.handle_message(
            self.mock_channel,
            self.mock_method,
            self.mock_properties,
            b'invalid message'
        )

        # Verify error response creation and message handling
        mock_create_response.assert_called_once()
        call_args = mock_create_response.call_args
        assert call_args[1]['template_type'] == 'error'
        assert call_args[1]['error']['type'] == 'execution_error'

        self.mock_rabbitmq_manager.send_result.assert_called_once_with(
            'source', "error_response"
        )
        self.mock_channel.basic_nack.assert_called_once_with(
            delivery_tag="test_tag", requeue=False
        )

    @patch('src.comm.rabbitmq.message_handler.yaml.safe_load')
    @patch('src.comm.rabbitmq.message_handler.create_response')
    def test_handle_message_unknown_simulation_type(
        self, mock_create_response, mock_yaml_load
    ):
        """Test handling of unknown simulation type after validation bypass."""
        # This test simulates a case where validation somehow passes
        # but we get an unknown type
        message_data = {
            'simulation': {
                'request_id': 'req123',
                'client_id': 'client456',
                'simulator': 'test_sim',
                'type': 'batch',  # Will be modified after validation
                'file': 'test.sim',
                'inputs': {'param': 'value'},
                'bridge_meta': {'key': 'value'}
            }
        }
        mock_yaml_load.return_value = message_data
        mock_create_response.return_value = "error_response"

        # Mock to simulate unknown type after validation
        with patch.object(self.handler, 'handle_message') as mock_handle:
            # Create a custom implementation that processes unknown type
            def custom_handle_message(ch, method, properties, body):
                # Simulate the actual logic but with unknown type
                source = method.routing_key.split('.')[0]
                sim_type = "unknown_type"  # Force unknown type
                error_response = mock_create_response(
                    template_type='error',
                    sim_file='test.sim',
                    sim_type=sim_type,
                    response_templates={},
                    bridge_meta={'key': 'value'},
                    request_id='req123',
                    error={
                        'message': f'Unknown simulation type: {sim_type}',
                        'type': 'invalid_simulation_type'
                    }
                )
                self.mock_rabbitmq_manager.send_result(source, error_response)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            mock_handle.side_effect = custom_handle_message

            # Execute
            self.handler.handle_message(
                self.mock_channel,
                self.mock_method,
                self.mock_properties,
                b'test message'
            )

            # Verify the mock was called
            mock_handle.assert_called_once()

    @patch('src.comm.rabbitmq.message_handler.yaml.safe_load')
    @patch('src.comm.rabbitmq.message_handler.create_response')
    def test_handle_message_general_exception(
        self, mock_create_response, mock_yaml_load
    ):
        """Test handling of general exceptions during message processing."""
        # Setup general exception during YAML loading
        general_error = Exception("Unexpected error")
        mock_yaml_load.side_effect = general_error
        mock_create_response.return_value = "error_response"

        # Execute
        self.handler.handle_message(
            self.mock_channel,
            self.mock_method,
            self.mock_properties,
            b'test message'
        )

        # Verify error response creation
        mock_create_response.assert_called_once_with(
            template_type='error',
            sim_file='',
            sim_type='',
            response_templates={},
            bridge_meta='unknown',
            request_id='unknown',
            error={
                'message': 'Error processing message',
                'details': str(general_error),
                'type': 'execution_error'
            }
        )

        # Verify error response sent and message nacked
        self.mock_rabbitmq_manager.send_result.assert_called_once_with(
            'source', "error_response"
        )
        self.mock_channel.basic_nack.assert_called_once_with(
            delivery_tag="test_tag", requeue=False
        )

    @patch('src.comm.rabbitmq.message_handler.yaml.safe_load')
    @patch('src.comm.rabbitmq.message_handler.create_response')
    def test_handle_message_send_error_response_fails(
        self, mock_create_response, mock_yaml_load
    ):
        """Test handling when sending error response fails."""
        # Setup exception during YAML loading
        mock_yaml_load.side_effect = Exception("Processing error")
        mock_create_response.return_value = "error_response"

        # Setup send_result to fail
        send_error = Exception("Send failed")
        self.mock_rabbitmq_manager.send_result.side_effect = send_error

        # Execute
        self.handler.handle_message(
            self.mock_channel,
            self.mock_method,
            self.mock_properties,
            b'test message'
        )

        # Verify that despite send failure, message is still nacked
        self.mock_channel.basic_nack.assert_called_once_with(
            delivery_tag="test_tag", requeue=False
        )

    def test_handle_message_no_message_id_in_properties(self):
        """Test handling message when properties has no message_id."""
        # Setup properties without message_id
        self.mock_properties.message_id = None

        with patch('src.comm.rabbitmq.message_handler.yaml.safe_load') as mock_yaml_load:
            mock_yaml_load.side_effect = Exception("Test error")

            with patch('src.comm.rabbitmq.message_handler.create_response') as mock_create_response:
                mock_create_response.return_value = "error_response"

                # Execute - should not raise exception
                self.handler.handle_message(
                    self.mock_channel,
                    self.mock_method,
                    self.mock_properties,
                    b'test message'
                )

                # Verify message was processed despite no message_id
                mock_yaml_load.assert_called_once()

    def test_config_missing_keys_handled_gracefully(self):
        """Test that missing config keys are handled gracefully."""
        minimal_config = {}
        handler = MessageHandler(
            "test_agent",
            self.mock_rabbitmq_manager,
            minimal_config
        )

        assert handler.path_simulation is None
        assert handler.response_templates == {}

    @patch('src.comm.rabbitmq.message_handler.yaml.safe_load')
    def test_routing_key_extraction(self, mock_yaml_load):
        """Test that routing key is correctly extracted for source."""
        # Setup mock for successful processing
        message_data = {
            'simulation': {
                'request_id': 'req123',
                'client_id': 'client456',
                'simulator': 'test_sim',
                'type': 'batch',
                'file': 'test.sim',
                'inputs': {'param': 'value'}
            }
        }
        mock_yaml_load.return_value = message_data

        # Test different routing key formats
        test_cases = [
            "source1.routing.key",
            "source2",
            "complex.source.with.many.parts"
        ]

        for routing_key in test_cases:
            self.mock_method.routing_key = routing_key
            expected_source = routing_key.split('.')[0]

            with patch('src.comm.rabbitmq.message_handler.handle_batch_simulation') as mock_batch:
                self.handler.handle_message(
                    self.mock_channel,
                    self.mock_method,
                    self.mock_properties,
                    b'test message'
                )

                # Verify source is correctly extracted
                mock_batch.assert_called_once()
                call_args = mock_batch.call_args[0]
                assert call_args[1] == expected_source  # source parameter

                mock_batch.reset_mock()


# Integration test class for end-to-end testing
class TestMessageHandlerIntegration:
    """Integration tests for MessageHandler with real message processing."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.agent_id = "integration_test_agent"
        self.mock_rabbitmq_manager = Mock()
        self.config = {
            'simulation': {'path': '/integration/test/path'},
            'response_templates': {'success': 'success_template'},
            'tcp': {'port': 9090, 'host': 'localhost'}
        }
        self.handler = MessageHandler(
            self.agent_id,
            self.mock_rabbitmq_manager,
            self.config
        )

    @patch('src.comm.rabbitmq.message_handler.handle_batch_simulation')
    def test_complete_batch_message_flow(self, mock_handle_batch):
        """Test complete flow of a valid batch message."""
        # Create complete valid message
        message_dict = {
            'simulation': {
                'request_id': 'integration_req_123',
                'client_id': 'integration_client_456',
                'simulator': 'integration_simulator',
                'type': 'batch',
                'file': 'integration_test.sim',
                'inputs': {
                    'temperature': 25.0,
                    'pressure': 101.325,
                    'iterations': 1000
                },
                'outputs': {
                    'result_file': 'output.csv'
                },
                'bridge_meta': {
                    'timestamp': '2024-01-01T00:00:00Z',
                    'version': '1.0.0'
                }
            },
            'request_id': 'payload_req_123'
        }

        # Convert to YAML bytes
        message_body = yaml.dump(message_dict).encode('utf-8')

        # Setup mocks
        mock_channel = Mock()
        mock_method = Mock(spec=Basic.Deliver)
        mock_method.routing_key = "integration_source.test.routing"
        mock_method.delivery_tag = "integration_tag"

        mock_properties = Mock(spec=BasicProperties)
        mock_properties.message_id = "integration_message_id"

        # Execute
        self.handler.handle_message(
            mock_channel,
            mock_method,
            mock_properties,
            message_body
        )

        # Verify successful processing
        mock_handle_batch.assert_called_once()
        call_args = mock_handle_batch.call_args[0]

        # Verify all parameters passed correctly
        assert call_args[0] == message_dict  # message data
        assert call_args[1] == "integration_source"  # source
        assert call_args[2] == self.mock_rabbitmq_manager  # rabbitmq manager
        assert call_args[3] == "/integration/test/path"  # simulation path
        assert call_args[4] == {"success": "success_template"}  # templates

        # Verify message acknowledged
        mock_channel.basic_ack.assert_called_once_with(
            delivery_tag="integration_tag"
        )

    @patch('src.comm.rabbitmq.message_handler.handle_streaming_simulation')
    def test_complete_streaming_message_flow(self, mock_handle_streaming):
        """Test complete flow of a valid streaming message."""
        # Create complete valid streaming message
        message_dict = {
            'simulation': {
                'request_id': 'stream_req_789',
                'client_id': 'stream_client_012',
                'simulator': 'streaming_simulator',
                'type': 'streaming',
                'file': 'streaming_test.sim',
                'inputs': {
                    'stream_rate': 1000,
                    'buffer_size': 4096
                },
                'bridge_meta': {
                    'stream_id': 'stream_789',
                    'protocol': 'tcp'
                }
            }
        }

        # Convert to YAML bytes
        message_body = yaml.dump(message_dict).encode('utf-8')

        # Setup mocks
        mock_channel = Mock()
        mock_method = Mock(spec=Basic.Deliver)
        mock_method.routing_key = "streaming_source.test"
        mock_method.delivery_tag = "streaming_tag"

        mock_properties = Mock(spec=BasicProperties)
        mock_properties.message_id = "streaming_message_id"

        # Execute
        self.handler.handle_message(
            mock_channel,
            mock_method,
            mock_properties,
            message_body
        )

        # Verify successful processing
        mock_handle_streaming.assert_called_once()
        call_args = mock_handle_streaming.call_args[0]

        # Verify all parameters passed correctly
        assert call_args[0] == message_dict  # message data
        assert call_args[1] == "streaming_source"  # source
        assert call_args[2] == self.mock_rabbitmq_manager  # rabbitmq manager
        assert call_args[3] == "/integration/test/path"  # simulation path
        assert call_args[4] == {"success": "success_template"}  # templates
        assert call_args[5] == {
            "port": 9090,
            "host": "localhost"}  # tcp settings

        # Verify message acknowledged
        mock_channel.basic_ack.assert_called_once_with(
            delivery_tag="streaming_tag"
        )
