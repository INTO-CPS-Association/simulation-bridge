import pytest
import yaml
from unittest.mock import MagicMock, patch

from src.comm.rabbitmq.message_handler import (
    MessageHandler, MessagePayload, SimulationData
)


class TestMessageHandler:
    """Test suite for the MessageHandler class."""

    @pytest.fixture(scope="function")
    def mock_rabbitmq_manager(self):
        """Fixture providing a mocked RabbitMQManager instance."""
        manager = MagicMock()
        manager.send_result = MagicMock()
        return manager

    @pytest.fixture(scope="function")
    def mock_channel(self):
        """Fixture providing a mocked RabbitMQ channel."""
        channel = MagicMock()
        channel.basic_ack = MagicMock()
        channel.basic_nack = MagicMock()
        return channel

    @pytest.fixture(scope="function")
    def basic_deliver(self):
        """Fixture providing basic delivery properties with simple routing key."""
        mock_deliver = MagicMock()
        mock_deliver.routing_key = "source.test_agent"
        mock_deliver.delivery_tag = 123
        return mock_deliver

    @pytest.fixture(scope="function")
    def complex_deliver(self):
        """Fixture providing delivery properties with complex routing key."""
        mock_deliver = MagicMock()
        mock_deliver.routing_key = "source.subtype.test_agent.additional"
        mock_deliver.delivery_tag = 123
        return mock_deliver

    @pytest.fixture(scope="function")
    def basic_properties(self):
        """Fixture providing message properties with message ID."""
        mock_properties = MagicMock()
        mock_properties.message_id = "test-message-id"
        return mock_properties

    @pytest.fixture(scope="function")
    def message_handler(self, mock_rabbitmq_manager):
        """Fixture providing a MessageHandler instance with mocked dependencies."""
        return MessageHandler(
            agent_id="test_agent",
            rabbitmq_manager=mock_rabbitmq_manager
        )

    @pytest.fixture(scope="function")
    def valid_batch_message(self):
        """Fixture providing a valid batch simulation message."""
        return yaml.dump({
            'simulation': {
                'simulator': 'test_simulator',
                'type': 'batch',
                'file': 'test_file.mat',
                'inputs': {'param1': 10}
            },
            'destinations': ['dest1'],
            'request_id': 'test-request-id'
        })

    @pytest.fixture(scope="function")
    def valid_streaming_message(self):
        """Fixture providing a valid streaming simulation message."""
        return yaml.dump({
            'simulation': {
                'simulator': 'test_simulator',
                'type': 'streaming',
                'file': 'test_file.mat',
                'inputs': {'param1': 10}
            },
            'destinations': ['dest1'],
            'request_id': 'test-request-id'
        })

    @pytest.fixture(scope="function")
    def invalid_yaml_message(self):
        """Fixture providing invalid YAML content."""
        return "invalid:yaml: ["

    @pytest.fixture(scope="function")
    def invalid_structure_message(self):
        """Fixture providing valid YAML with invalid message structure."""
        return yaml.dump({
            'simulation': {
                'type': 'batch',
                'file': 'test_file.mat',
                'inputs': {'param1': 10}
            },
            'destinations': ['dest1']
        })

    def test_handle_batch_message(
        self, message_handler, mock_channel, basic_deliver,
        basic_properties, valid_batch_message
    ):
        """Test successful handling of batch simulation message."""
        with patch("src.comm.rabbitmq.message_handler.handle_batch_simulation") as mock_batch:
            message_handler.handle_message(
                mock_channel,
                basic_deliver,
                basic_properties,
                valid_batch_message.encode())

            mock_batch.assert_called_once()
            mock_channel.basic_ack.assert_called_once_with(delivery_tag=123)
            mock_channel.basic_nack.assert_not_called()

    def test_handle_streaming_message(
        self, message_handler, mock_channel, basic_deliver,
        basic_properties, valid_streaming_message
    ):
        """Test successful handling of streaming simulation message."""
        with patch("src.comm.rabbitmq.message_handler.handle_streaming_simulation") as mock_stream:
            message_handler.handle_message(
                mock_channel,
                basic_deliver,
                basic_properties,
                valid_streaming_message.encode())

            # Verify ack happens before processing
            mock_channel.basic_ack.assert_called_once_with(delivery_tag=123)
            mock_stream.assert_called_once()

    def test_invalid_yaml_handling(
        self, message_handler, mock_channel, basic_deliver,
        basic_properties, invalid_yaml_message
    ):
        """Test handling of invalid YAML content."""
        message_handler.handle_message(
            mock_channel,
            basic_deliver,
            basic_properties,
            invalid_yaml_message.encode())

        mock_channel.basic_nack.assert_called_once_with(
            delivery_tag=123, requeue=False)
        message_handler.rabbitmq_manager.send_result.assert_called_once()
        error_response = message_handler.rabbitmq_manager.send_result.call_args[0][1]
        assert error_response['status'] == 'error'
        assert 'YAML parsing error' in error_response['error']['message']

    def test_invalid_message_structure(
        self, message_handler, mock_channel, basic_deliver,
        basic_properties, invalid_structure_message
    ):
        """Test handling of valid YAML with invalid structure."""
        message_handler.handle_message(
            mock_channel,
            basic_deliver,
            basic_properties,
            invalid_structure_message.encode())

        mock_channel.basic_nack.assert_called_once_with(
            delivery_tag=123, requeue=False)
        message_handler.rabbitmq_manager.send_result.assert_called_once()
        error_response = message_handler.rabbitmq_manager.send_result.call_args[0][1]
        assert error_response['status'] == 'error'
        assert 'Message validation failed' in error_response['error']['message']

    def test_batch_processing_error(
        self, message_handler, mock_channel, basic_deliver,
        basic_properties, valid_batch_message
    ):
        """Test error handling during batch processing."""
        with patch(
            "src.comm.rabbitmq.message_handler.handle_batch_simulation",
            side_effect=Exception("Batch error")
        ):
            message_handler.handle_message(
                mock_channel,
                basic_deliver,
                basic_properties,
                valid_batch_message.encode())

            mock_channel.basic_nack.assert_called_once_with(
                delivery_tag=123, requeue=False)
            error_response = message_handler.rabbitmq_manager.send_result.call_args[0][1]
            assert 'Batch error' in error_response['error']['details']

    def test_pydantic_validation(self):
        """Test Pydantic model validation scenarios."""
        # Valid batch request
        valid_data = {
            'simulation': {
                'simulator': 'test',
                'type': 'batch',
                'file': 'test.mat',
                'inputs': {'param': 10}
            },
            'destinations': ['dest1']
        }
        payload = MessagePayload(**valid_data)
        assert payload.request_id  # Should be generated

        # Invalid simulation type
        with pytest.raises(ValueError):
            SimulationData(
                simulator='test',
                type='invalid',
                file='test.mat',
                inputs={'param': 10}
            )

    def test_complex_routing_key(
        self, message_handler, mock_channel, complex_deliver,
        basic_properties, valid_batch_message
    ):
        """Test handling of messages with complex routing keys."""
        with patch("src.comm.rabbitmq.message_handler.handle_batch_simulation") as mock_batch:
            message_handler.handle_message(
                mock_channel,
                complex_deliver,
                basic_properties,
                valid_batch_message.encode())

            mock_batch.assert_called_once()
            assert mock_batch.call_args[0][1] == "source"

    def test_missing_message_id(
        self, message_handler, mock_channel, basic_deliver,
        valid_batch_message
    ):
        """Test handling of messages missing message ID."""
        mock_properties = MagicMock()
        mock_properties.message_id = None

        message_handler.handle_message(
            mock_channel,
            basic_deliver,
            mock_properties,
            valid_batch_message.encode())

        mock_channel.basic_ack.assert_called_once_with(delivery_tag=123)

    def test_error_response_failure(
        self, message_handler, mock_channel, basic_deliver,
        basic_properties, valid_batch_message
    ):
        """Test error handling when sending error responses fails."""
        with patch("src.comm.rabbitmq.message_handler.handle_batch_simulation", side_effect=Exception("Processing error")), \
                patch("src.comm.rabbitmq.message_handler.create_response", return_value="fake_response"):
            message_handler.handle_message(
                mock_channel,
                basic_deliver,
                basic_properties,
                valid_batch_message.encode())
            mock_channel.basic_nack.assert_called_once_with(
                delivery_tag=123, requeue=False)
