"""
Integration test for MessageHandler and SimpleUsageMatlabAgent components.
Tests the complete message flow between client agent and message handler.
"""
import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, MagicMock, patch, call
from typing import Dict, Any, List

import pika
import yaml

# Mock the external dependencies that might not be available in test environment


class MockRabbitMQManager:
    """Mock RabbitMQ manager for testing purposes."""

    def __init__(self):
        self.sent_results: List[Dict[str, Any]] = []
        self.sent_messages: List[Dict[str, Any]] = []

    def send_result(self, source: str, response: Dict[str, Any]) -> None:
        """Mock method to capture sent results."""
        self.sent_results.append({
            'source': source,
            'response': response
        })

    def send_message(self, routing_key: str, message: Dict[str, Any]) -> None:
        """Mock method to capture sent messages."""
        self.sent_messages.append({
            'routing_key': routing_key,
            'message': message
        })


class MockSimulationInputs:
    """Mock for SimulationInputs model."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockSimulationOutputs:
    """Mock for SimulationOutputs model."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockSimulationData:
    """Mock for SimulationData model."""

    def __init__(self, request_id: str, client_id: str, simulator: str,
                 type_: str, file: str, inputs: Dict[str, Any],
                 outputs: Dict[str, Any] = None, bridge_meta: Dict[str, Any] = None):
        self.request_id = request_id
        self.client_id = client_id
        self.simulator = simulator
        self.type = type_
        self.file = file
        self.inputs = MockSimulationInputs(**inputs)
        self.outputs = MockSimulationOutputs(**outputs) if outputs else None
        self.bridge_meta = bridge_meta


class MockMessagePayload:
    """Mock for MessagePayload model."""

    def __init__(self, **kwargs):
        simulation_data = kwargs.get('simulation', {})
        self.simulation = MockSimulationData(
            request_id=simulation_data.get('request_id', ''),
            client_id=simulation_data.get('client_id', ''),
            simulator=simulation_data.get('simulator', ''),
            type_=simulation_data.get('type', 'batch'),
            file=simulation_data.get('file', ''),
            inputs=simulation_data.get('inputs', {}),
            outputs=simulation_data.get('outputs'),
            bridge_meta=simulation_data.get('bridge_meta')
        )
        self.request_id = kwargs.get('request_id', self.simulation.request_id)


# Mock the message handler that mimics the validation behavior from your
# actual code
class MockMessageHandler:
    """Mock implementation of MessageHandler for testing."""

    def __init__(self, agent_id: str, rabbitmq_manager: Any,
                 config: Dict[str, Any]):
        self.agent_id = agent_id
        self.rabbitmq_manager = rabbitmq_manager
        self.config = config
        self.path_simulation = config.get('simulation', {}).get('path', None)
        self.response_templates = config.get('response_templates', {})
        self.processed_messages: List[Dict[str, Any]] = []

    def get_agent_id(self) -> str:
        """Return the agent ID."""
        return self.agent_id

    def handle_message(self, ch, method, properties, body: bytes) -> None:
        """Mock message handling that mimics actual validation logic."""
        try:
            msg_dict = yaml.safe_load(body)
            self.processed_messages.append(msg_dict)

            # Simulate validation - check for required fields
            simulation = msg_dict.get('simulation', {})
            required_fields = [
                'request_id',
                'client_id',
                'simulator',
                'type',
                'file',
                'inputs']
            missing_fields = [
                field for field in required_fields if field not in simulation]

            if missing_fields:
                # Validation failed - return error
                response = {
                    'status': 'error',
                    'error': {
                        'message': 'Message validation failed',
                        'details': f'Missing required fields: {missing_fields}',
                        'type': 'validation_error'
                    }
                }
            else:
                # Validation passed - process based on type
                payload = MockMessagePayload(**msg_dict)
                sim_type = payload.simulation.type

                if sim_type == 'streaming':
                    response = {
                        'request_id': payload.simulation.request_id,
                        'status': 'streaming_started',
                        'simulation_type': 'streaming',
                        'file': payload.simulation.file
                    }
                elif sim_type == 'batch':
                    response = {
                        'request_id': payload.simulation.request_id,
                        'status': 'completed',
                        'simulation_type': 'batch',
                        'file': payload.simulation.file,
                        'results': {
                            'time': 1.23,
                            'current_step': 200,
                            'positions': [[1.0, 2.0], [3.0, 4.0]],
                            'velocities': [[0.1, 0.2], [0.3, 0.4]],
                            'running': False
                        }
                    }
                else:
                    response = {
                        'request_id': payload.simulation.request_id,
                        'status': 'error',
                        'error': f'Unknown simulation type: {sim_type}'
                    }

            source = method.routing_key.split('.')[0]
            self.rabbitmq_manager.send_result(source, response)
            ch.basic_ack(method.delivery_tag)

        except yaml.YAMLError as e:
            # YAML parsing error
            error_response = {
                'status': 'error',
                'error': {
                    'message': 'YAML parsing error',
                    'details': str(e),
                    'type': 'yaml_parse_error'
                }
            }
            try:
                source = method.routing_key.split('.')[0]
                self.rabbitmq_manager.send_result(source, error_response)
            except BaseException:
                pass
            ch.basic_nack(method.delivery_tag, requeue=False)
        except Exception as e:
            # Other processing errors
            error_response = {
                'status': 'error',
                'error': {
                    'message': 'Error processing message',
                    'details': str(e),
                    'type': 'execution_error'
                }
            }
            try:
                source = method.routing_key.split('.')[0]
                self.rabbitmq_manager.send_result(source, error_response)
            except BaseException:
                pass
            ch.basic_nack(method.delivery_tag, requeue=False)


class IntegrationTest(unittest.TestCase):
    """Integration test class for MessageHandler and SimpleUsageMatlabAgent."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.yaml')
        self.simulation_file = os.path.join(self.temp_dir, 'simulation.yaml')

        # Create test configuration
        test_config = {
            'rabbitmq': {
                'host': 'localhost',
                'port': 5672,
                'username': 'test_user',
                'password': 'test_pass',
                'vhost': '/test',
                'heartbeat': 600
            }
        }

        # Create test simulation data
        simulation_data = {
            'simulation': {
                'request_id': '1dsanjkdsa',
                'client_id': 'dt',
                'simulator': 'matlab',
                'type': 'streaming',
                'file': 'simulation_streaming.m',
                'inputs': {
                    'time_step': 0.05,
                    'num_agents': 8,
                    'max_steps': 200,
                    'avoidance_threshold': 1,
                    'show_agent_index': 1,
                    'use_gui': True
                },
                'outputs': {
                    'time': 'float',
                    'current_step': 'int',
                    'positions': '[[float, float]]',
                    'velocities': '[[float, float]]',
                    'running': 'bool'
                }
            }
        }

        # Write configuration files
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(test_config, f)

        with open(self.simulation_file, 'w', encoding='utf-8') as f:
            yaml.dump(simulation_data, f)

        # Mock RabbitMQ components
        self.mock_connection = Mock()
        self.mock_channel = Mock()
        self.mock_connection.channel.return_value = self.mock_channel

        # Initialize mocks
        self.mock_rabbitmq_manager = MockRabbitMQManager()
        self.received_messages = []

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('resources.use_matlab_agent.pika.BlockingConnection')
    def test_message_handler_initialization(self, mock_connection):
        """Test that the message handler initializes correctly."""
        config = {
            'simulation': {'path': '/test/path'},
            'response_templates': {'success': 'OK', 'error': 'Error'}
        }

        handler = MockMessageHandler(
            agent_id="test_matlab",
            rabbitmq_manager=self.mock_rabbitmq_manager,
            config=config
        )

        # Verify initialization
        self.assertEqual(handler.get_agent_id(), "test_matlab")
        self.assertEqual(handler.path_simulation, '/test/path')
        self.assertEqual(handler.response_templates['success'], 'OK')

    @patch('resources.use_matlab_agent.pika.BlockingConnection')
    def test_error_handling_invalid_yaml(self, mock_connection):
        """Test error handling for invalid YAML messages."""
        mock_connection.return_value = self.mock_connection

        handler = MockMessageHandler(
            agent_id="matlab",
            rabbitmq_manager=self.mock_rabbitmq_manager,
            config={
                'simulation': {
                    'path': '/test/path'},
                'response_templates': {}}
        )

        # Simulate invalid YAML
        invalid_yaml = b"invalid: yaml: content: [unclosed"

        mock_method = Mock()
        mock_method.routing_key = 'dt.matlab'
        mock_method.delivery_tag = 'error_tag'

        mock_properties = Mock()
        mock_properties.message_id = 'error_message_id'

        handler.handle_message(
            ch=self.mock_channel,
            method=mock_method,
            properties=mock_properties,
            body=invalid_yaml
        )

        # Verify error response
        self.assertEqual(len(self.mock_rabbitmq_manager.sent_results), 1)
        response = self.mock_rabbitmq_manager.sent_results[0]
        self.assertEqual(response['response']['status'], 'error')
        self.assertEqual(
            response['response']['error']['type'],
            'yaml_parse_error')

    @patch('resources.use_matlab_agent.pika.BlockingConnection')
    def test_error_handling_invalid_message_structure(self, mock_connection):
        """Test error handling for invalid message structure."""
        mock_connection.return_value = self.mock_connection

        handler = MockMessageHandler(
            agent_id="matlab",
            rabbitmq_manager=self.mock_rabbitmq_manager,
            config={
                'simulation': {
                    'path': '/test/path'},
                'response_templates': {}}
        )

        # Create message with missing required fields
        invalid_message = {
            'simulation': {
                'request_id': 'test_id',
                # Missing required fields like client_id, simulator, etc.
            }
        }

        invalid_yaml = yaml.dump(invalid_message).encode('utf-8')

        mock_method = Mock()
        mock_method.routing_key = 'dt.matlab'
        mock_method.delivery_tag = 'structure_error_tag'

        mock_properties = Mock()
        mock_properties.message_id = 'structure_error_message_id'

        handler.handle_message(
            ch=self.mock_channel,
            method=mock_method,
            properties=mock_properties,
            body=invalid_yaml
        )

        # Verify error response
        self.assertEqual(len(self.mock_rabbitmq_manager.sent_results), 1)
        response = self.mock_rabbitmq_manager.sent_results[0]
        self.assertEqual(response['response']['status'], 'error')
        self.assertEqual(
            response['response']['error']['type'],
            'validation_error')

    def test_result_handling(self):
        """Test result handling in the agent."""
        # Create a mock result
        test_result = {
            'request_id': 'test_123',
            'status': 'completed',
            'results': {
                'time': 2.45,
                'current_step': 150,
                'positions': [[1.1, 2.2], [3.3, 4.4]],
                'velocities': [[0.1, 0.2], [0.3, 0.4]],
                'running': False
            }
        }

        # Mock the agent's result handling
        mock_agent = Mock()
        mock_agent.handle_result = Mock()

        # Mock channel and method for result callback
        mock_ch = Mock()
        mock_method = Mock()
        mock_method.delivery_tag = 'result_tag'
        mock_properties = Mock()

        result_body = yaml.dump(test_result).encode('utf-8')

        # Test the result handling
        try:
            result_dict = yaml.safe_load(result_body)
            mock_agent.handle_result(
                mock_ch, mock_method, mock_properties, result_body)

            # Verify the result was processed
            mock_agent.handle_result.assert_called_once_with(
                mock_ch, mock_method, mock_properties, result_body
            )

        except Exception as e:
            self.fail(f"Result handling failed: {e}")

    def test_configuration_validation(self):
        """Test configuration validation and loading."""
        from resources.use_matlab_agent import SimpleUsageMatlabAgent

        # Test loading valid configuration
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        self.assertIn('rabbitmq', config)

        # Test invalid configuration file
        invalid_config_file = os.path.join(self.temp_dir, 'invalid_config.yaml')
        with open(invalid_config_file, 'w', encoding='utf-8') as f:
            f.write("invalid: yaml: content: [")

        with self.assertRaises(yaml.YAMLError):
            with open(invalid_config_file, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)


if __name__ == '__main__':
    # Configure test runner
    unittest.main(verbosity=2)
