import pytest
from unittest import mock
from unittest.mock import MagicMock, patch
import yaml
from src.handlers.message_handler import MessageHandler

# Import functions from batch and streaming
from src.batch.batch import handle_batch_simulation
from src.streaming.streaming import handle_streaming_simulation


@pytest.fixture
def mock_rabbitmq_manager():
    """Create a mock for RabbitMQManager."""
    return MagicMock()


@pytest.fixture
def mock_channel():
    """Create a mock for the RabbitMQ channel."""
    return MagicMock()


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


def test_handle_message_batch(
    message_handler, mock_channel, basic_deliver, basic_properties
):
    """Test handling of a 'batch' type message."""
    body = yaml.dump({
        'simulation': {'type': 'batch'},
        'data': 'sample_data'
    })

    # Patch the batch simulation handler
    with patch("src.handlers.message_handler.handle_batch_simulation") as mock_handle_batch:
        message_handler.handle_message(
            ch=mock_channel,
            method=basic_deliver,
            properties=basic_properties,
            body=body.encode()
        )

        # Verify the batch function is called with correct arguments
        mock_handle_batch.assert_called_once_with(
            yaml.safe_load(body),
            "source",
            message_handler.rabbitmq_manager
        )
        
        # Verify acknowledgment is sent
        mock_channel.basic_ack.assert_called_once_with(delivery_tag=123)


def test_handle_message_streaming(
    message_handler, mock_channel, basic_deliver, basic_properties
):
    """Test handling of a 'streaming' type message."""
    body = yaml.dump({
        'simulation': {'type': 'streaming'},
        'data': 'sample_data'
    })

    # Patch the streaming simulation handler
    with patch("src.handlers.message_handler.handle_streaming_simulation") as mock_handle_streaming:
        message_handler.handle_message(
            ch=mock_channel,
            method=basic_deliver,
            properties=basic_properties,
            body=body.encode()
        )

        # Verify the streaming function is called with correct arguments
        mock_handle_streaming.assert_called_once_with(
            yaml.safe_load(body),
            "source",
            message_handler.rabbitmq_manager
        )
        
        # Verify acknowledgment is sent
        mock_channel.basic_ack.assert_called_once_with(delivery_tag=123)


def test_handle_message_unknown_type(
    message_handler, mock_channel, basic_deliver, basic_properties
):
    """Test handling of a message with an unknown type."""
    body = yaml.dump({
        'simulation': {'type': 'unknown_type'},
        'data': 'sample_data'
    })

    message_handler.handle_message(
        ch=mock_channel,
        method=basic_deliver,
        properties=basic_properties,
        body=body.encode()
    )

    # Verify neither acknowledgment nor negative acknowledgment is sent
    mock_channel.basic_ack.assert_not_called()
    mock_channel.basic_nack.assert_not_called()


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
    mock_channel.basic_nack.assert_called_once_with(delivery_tag=123)


def test_handle_message_general_exception(
    message_handler, mock_channel, basic_deliver, basic_properties
):
    """Test behavior when a general exception is raised."""
    body = yaml.dump({
        'simulation': {'type': 'batch'},
        'data': 'sample_data'
    })

    # Patch the batch simulation handler to raise an exception
    with patch("src.handlers.message_handler.handle_batch_simulation", side_effect=Exception("Generic Error")):
        message_handler.handle_message(
            ch=mock_channel,
            method=basic_deliver,
            properties=basic_properties,
            body=body.encode()
        )

        # Verify negative acknowledgment is sent in case of an error
        mock_channel.basic_nack.assert_called_once_with(delivery_tag=123)

