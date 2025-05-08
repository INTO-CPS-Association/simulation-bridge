import pytest
import yaml
import json
from unittest.mock import MagicMock, patch
from src.handlers.message_handler import MessageHandler, MessagePayload, SimulationData

# Import functions from batch and streaming modules
from src.batch.batch import handle_batch_simulation
from src.streaming.streaming import handle_streaming_simulation


@pytest.fixture
def mock_rabbitmq_manager():
    """Create a mock for RabbitMQManager."""
    manager = MagicMock()
    manager.send_result = MagicMock()
    return manager


@pytest.fixture
def mock_channel():
    """Create a mock for the RabbitMQ channel."""
    channel = MagicMock()
    channel.basic_ack = MagicMock()
    channel.basic_nack = MagicMock()
    return channel


@pytest.fixture
def message_handler(mock_rabbitmq_manager):
    """Instantiate a MessageHandler with a mocked RabbitMQManager."""
    return MessageHandler(agent_id="test_agent", rabbitmq_manager=mock_rabbitmq_manager)


@pytest.fixture
def basic_deliver():
    """Mock the Basic.Deliver method."""
    mock_deliver = MagicMock()
    mock_deliver.routing_key = "source.test_agent"
    mock_deliver.delivery_tag = 123
    return mock_deliver


@pytest.fixture
def basic_properties():
    """Mock the message properties."""
    mock_properties = MagicMock()
    mock_properties.message_id = "test-message-id"
    return mock_properties


@pytest.fixture
def valid_batch_message():
    """Create a valid batch message."""
    return yaml.dump({
        'simulation': {
            'simulator': 'test_simulator',
            'type': 'batch',
            'file': 'test_file.mat',
            'inputs': {'param1': 10, 'param2': 'test'}
        },
        'destinations': ['dest1', 'dest2'],
        'request_id': 'test-request-id'
    })


@pytest.fixture
def valid_streaming_message():
    """Create a valid streaming message."""
    return yaml.dump({
        'simulation': {
            'simulator': 'test_simulator',
            'type': 'streaming',
            'file': 'test_file.mat',
            'inputs': {'param1': 10, 'param2': 'test'}
        },
        'destinations': ['dest1', 'dest2'],
        'request_id': 'test-request-id'
    })


def test_handle_message_batch(
    message_handler, mock_channel, basic_deliver, basic_properties, valid_batch_message
):
    """Test handling of a 'batch' type message."""
    # Patch the batch simulation handler
    with patch("src.handlers.message_handler.handle_batch_simulation") as mock_handle_batch:
        message_handler.handle_message(
            ch=mock_channel,
            method=basic_deliver,
            properties=basic_properties,
            body=valid_batch_message.encode()
        )

        # Verify the batch function is called with correct arguments
        mock_handle_batch.assert_called_once()
        args = mock_handle_batch.call_args[0]
        assert args[0] == yaml.safe_load(valid_batch_message)
        assert args[1] == "source"
        assert args[2] == message_handler.rabbitmq_manager

        # Verify acknowledgment is sent
        mock_channel.basic_ack.assert_called_once_with(delivery_tag=123)


def test_handle_message_streaming(
    message_handler, mock_channel, basic_deliver, basic_properties, valid_streaming_message
):
    """Test handling of a 'streaming' type message."""
    # Patch the streaming simulation handler
    with patch("src.handlers.message_handler.handle_streaming_simulation") as mock_handle_streaming:
        message_handler.handle_message(
            ch=mock_channel,
            method=basic_deliver,
            properties=basic_properties,
            body=valid_streaming_message.encode()
        )

        # Verify the streaming function is called with correct arguments
        mock_handle_streaming.assert_called_once()
        args = mock_handle_streaming.call_args[0]
        assert args[0] == yaml.safe_load(valid_streaming_message)
        assert args[1] == "source"
        assert args[2] == message_handler.rabbitmq_manager

        # Verify acknowledgment is sent before handling streaming (asynchronous pattern)
        mock_channel.basic_ack.assert_called_once_with(delivery_tag=123)


def test_handle_message_invalid_yaml(
    message_handler, mock_channel, basic_deliver, basic_properties
):
    """Test handling of a message with invalid YAML."""
    body = "this is not valid yaml: ["

    message_handler.handle_message(
        ch=mock_channel,
        method=basic_deliver,
        properties=basic_properties,
        body=body.encode()
    )

    # Verify negative acknowledgment is sent
    mock_channel.basic_nack.assert_called_once_with(
        delivery_tag=123, requeue=False)

    # Verify error response is sent
    message_handler.rabbitmq_manager.send_result.assert_called_once()
    error_response = message_handler.rabbitmq_manager.send_result.call_args[0][1]
    assert error_response['status'] == 'error'
    assert 'YAML parsing error' in error_response['error']['message']


def test_handle_message_invalid_structure(
    message_handler, mock_channel, basic_deliver, basic_properties
):
    """Test handling of a message with valid YAML but invalid structure."""
    body = yaml.dump({
        'simulation': {
            # Missing required 'simulator' field
            'type': 'batch',
            'file': 'test_file.mat',
            'inputs': {'param1': 10}
        },
        'destinations': ['dest1']
    })

    message_handler.handle_message(
        ch=mock_channel,
        method=basic_deliver,
        properties=basic_properties,
        body=body.encode()
    )

    # Verify negative acknowledgment is sent
    mock_channel.basic_nack.assert_called_once_with(
        delivery_tag=123, requeue=False)

    # Verify error response is sent
    message_handler.rabbitmq_manager.send_result.assert_called_once()
    error_response = message_handler.rabbitmq_manager.send_result.call_args[0][1]
    assert error_response['status'] == 'error'
    assert 'Message validation failed' in error_response['error']['message']


def test_handle_message_invalid_simulation_type(
    message_handler, mock_channel, basic_deliver, basic_properties
):
    """Test handling of a message with an invalid simulation type."""
    # We need to bypass the Pydantic validation to test this path
    body = yaml.dump({
        'simulation': {
            'simulator': 'test_simulator',
            'type': 'invalid_type',  # Invalid type
            'file': 'test_file.mat',
            'inputs': {'param1': 10}
        },
        'destinations': ['dest1'],
        'request_id': 'test-id'
    })

    # Patch the Pydantic validator to let the invalid type through
    with patch("src.handlers.message_handler.MessagePayload", autospec=True) as mock_payload:
        # Configure the mock to return a valid object with the invalid type
        mock_instance = MagicMock()
        mock_instance.simulation.type = 'invalid_type'
        mock_instance.simulation.file = 'test_file.mat'
        mock_payload.return_value = mock_instance

        message_handler.handle_message(
            ch=mock_channel,
            method=basic_deliver,
            properties=basic_properties,
            body=body.encode()
        )

        # Verify negative acknowledgment is sent
        mock_channel.basic_nack.assert_called_once_with(
            delivery_tag=123, requeue=False)

        # Verify error response is sent
        message_handler.rabbitmq_manager.send_result.assert_called_once()
        error_response = message_handler.rabbitmq_manager.send_result.call_args[0][1]
        assert error_response['status'] == 'error'
        assert 'Unknown simulation type' in error_response['error']['message']


def test_handle_message_batch_error(
    message_handler, mock_channel, basic_deliver, basic_properties, valid_batch_message
):
    """Test handling when batch simulation handler raises an exception."""
    # Patch the batch simulation handler to raise an exception
    with patch("src.handlers.message_handler.handle_batch_simulation",
               side_effect=Exception("Batch processing error")):

        message_handler.handle_message(
            ch=mock_channel,
            method=basic_deliver,
            properties=basic_properties,
            body=valid_batch_message.encode()
        )

        # Verify negative acknowledgment is sent
        mock_channel.basic_nack.assert_called_once_with(
            delivery_tag=123, requeue=False)

        # Verify error response is sent
        message_handler.rabbitmq_manager.send_result.assert_called_once()
        error_response = message_handler.rabbitmq_manager.send_result.call_args[0][1]
        assert error_response['status'] == 'error'
        assert 'Error processing message' in error_response['error']['message']
        assert 'Batch processing error' in error_response['error'].get(
            'details', '')


def test_handle_message_error_response_failure(
    message_handler, mock_channel, basic_deliver, basic_properties, valid_batch_message
):
    """Test handling when both processing and sending error response fails."""
    # Patch batch handler to raise exception and rabbitmq_manager to also raise exception
    with patch("src.handlers.message_handler.handle_batch_simulation",
               side_effect=Exception("Batch processing error")):

        # Also make the send_result method fail
        message_handler.rabbitmq_manager.send_result.side_effect = Exception(
            "Send error")

        message_handler.handle_message(
            ch=mock_channel,
            method=basic_deliver,
            properties=basic_properties,
            body=valid_batch_message.encode()
        )

        # Verify negative acknowledgment is sent
        mock_channel.basic_nack.assert_called_once_with(
            delivery_tag=123, requeue=False)

        # Verify we tried to send an error response
        message_handler.rabbitmq_manager.send_result.assert_called_once()


def test_pydantic_model_validation():
    """Test the Pydantic model validation."""
    # Valid data
    valid_data = {
        'simulation': {
            'simulator': 'test_simulator',
            'type': 'batch',
            'file': 'test_file.mat',
            'inputs': {'param1': 10}
        },
        'destinations': ['dest1', 'dest2'],
        'request_id': 'test-id'
    }

    # Should not raise an exception
    payload = MessagePayload(**valid_data)
    assert payload.simulation.type == 'batch'
    assert payload.simulation.file == 'test_file.mat'
    assert payload.simulation.inputs.param1 == 10
    assert payload.destinations == ['dest1', 'dest2']
    assert payload.request_id == 'test-id'

    # Test the validator for simulation type
    with pytest.raises(ValueError) as exc_info:
        SimulationData(
            simulator='test_simulator',
            type='invalid_type',  # Invalid type
            file='test_file.mat',
            inputs={'param1': 10}
        )
    assert "Invalid simulation type" in str(exc_info.value)


def test_handle_message_with_no_message_id(
    message_handler, mock_channel, basic_deliver, valid_batch_message
):
    """Test handling of a message with no message_id."""
    # Create properties with no message_id
    properties = MagicMock()
    properties.message_id = None

    with patch("src.handlers.message_handler.handle_batch_simulation") as mock_handle_batch:
        message_handler.handle_message(
            ch=mock_channel,
            method=basic_deliver,
            properties=properties,
            body=valid_batch_message.encode()
        )

        # Processing should still work
        mock_handle_batch.assert_called_once()

        # Verify acknowledgment is sent
        mock_channel.basic_ack.assert_called_once_with(delivery_tag=123)


def test_message_handler_initialization():
    """Test that MessageHandler initializes correctly."""
    rabbitmq_manager = MagicMock()
    handler = MessageHandler(agent_id="test_agent",
                             rabbitmq_manager=rabbitmq_manager)

    assert handler.agent_id == "test_agent"
    assert handler.rabbitmq_manager == rabbitmq_manager


def test_handle_message_with_complex_routing_key(
    message_handler, mock_channel, basic_properties, valid_batch_message
):
    """Test handling of a message with a complex routing key."""
    # Create a delivery with a complex routing key
    complex_deliver = MagicMock()
    complex_deliver.routing_key = "source.subtype.test_agent.additional"
    complex_deliver.delivery_tag = 123

    with patch("src.handlers.message_handler.handle_batch_simulation") as mock_handle_batch:
        message_handler.handle_message(
            ch=mock_channel,
            method=complex_deliver,
            properties=basic_properties,
            body=valid_batch_message.encode()
        )

        # Processing should still extract the correct source
        mock_handle_batch.assert_called_once()
        assert mock_handle_batch.call_args[0][1] == "source"
