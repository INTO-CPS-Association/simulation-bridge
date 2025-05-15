import pytest
from unittest import mock
from unittest.mock import MagicMock

import pika
from pika import BasicProperties
from pika.exceptions import AMQPError, ChannelClosedByBroker

from agents.matlab.matlab_agent.src.comm.rabbitmq.rabbitmq_manager import RabbitMQManager


@pytest.fixture
def mock_config():
    """Fixture providing a standardized RabbitMQ configuration for tests."""
    return {
        "rabbitmq": {
            "host": "localhost",
            "port": 5672,
            "username": "guest",
            "password": "guest",
            "heartbeat": 600
        },
        "exchanges": {
            "input": "ex.bridge.output",
            "output": "ex.sim.result"
        },
        "queue": {
            "durable": True,
            "prefetch_count": 1
        }
    }


@pytest.fixture
def agent_id():
    """Fixture providing a standardized agent ID for tests."""
    return "test_agent"


@pytest.fixture
def mock_connection():
    """
    Fixture providing a mock for Pika connection and channel.

    Returns:
        tuple: (mocked_connection, mocked_channel)
    """
    with mock.patch("src.core.rabbitmq_manager.pika.BlockingConnection") as mocked_connection:
        mocked_channel = MagicMock()
        mocked_connection.return_value.channel.return_value = mocked_channel
        yield mocked_connection, mocked_channel


@pytest.fixture
def rabbitmq_manager(mock_connection, mock_config, agent_id):
    """
    Fixture creating a pre-configured RabbitMQManager instance.

    Returns:
        RabbitMQManager: Configured instance with mocked connections
    """
    return RabbitMQManager(agent_id, mock_config)


def test_initialization(mock_connection, mock_config, agent_id):
    """Test RabbitMQManager initialization configures connections properly."""
    mocked_connection, mocked_channel = mock_connection

    # Create manager instance
    RabbitMQManager(agent_id, mock_config)

    # Verify connection setup
    mocked_connection.assert_called_once()

    # Verify exchanges are properly declared
    mocked_channel.exchange_declare.assert_any_call(
        exchange="ex.bridge.output", exchange_type="topic", durable=True)
    mocked_channel.exchange_declare.assert_any_call(
        exchange="ex.sim.result", exchange_type="topic", durable=True)

    # Verify queue setup
    mocked_channel.queue_declare.assert_called_once_with(
        queue=f"Q.sim.{agent_id}", durable=True)
    mocked_channel.queue_bind.assert_called_once_with(
        exchange="ex.bridge.output",
        queue=f"Q.sim.{agent_id}",
        routing_key=f"*.{agent_id}")

    # Verify QoS settings
    mocked_channel.basic_qos.assert_called_once_with(prefetch_count=1)


def test_register_message_handler(rabbitmq_manager):
    """Test message handler registration."""
    def mock_handler(*args):
        pass

    # Register handler and verify it's stored
    rabbitmq_manager.register_message_handler(mock_handler)
    assert rabbitmq_manager.message_handler == mock_handler


def test_start_consuming_with_handler(rabbitmq_manager, mock_connection):
    """Test starting message consumption with registered handler."""
    _, mocked_channel = mock_connection

    def mock_handler(*args):
        pass

    # Register handler and start consuming
    rabbitmq_manager.register_message_handler(mock_handler)
    rabbitmq_manager.start_consuming()

    # Verify consumer is set up correctly
    mocked_channel.basic_consume.assert_called_once_with(
        queue=f"Q.sim.{rabbitmq_manager.agent_id}",
        on_message_callback=mock_handler
    )
    mocked_channel.start_consuming.assert_called_once()


def test_start_consuming_without_handler(rabbitmq_manager, mock_connection):
    """Test that start_consuming without a handler doesn't call basic_consume or start_consuming."""
    _, mocked_channel = mock_connection

    # Start consuming without registering a handler
    rabbitmq_manager.start_consuming()

    # Verify that consumption methods aren't called
    mocked_channel.basic_consume.assert_not_called()
    mocked_channel.start_consuming.assert_not_called()


def test_send_message_success(rabbitmq_manager, mock_connection):
    """Test successful message sending."""
    _, mocked_channel = mock_connection

    # Send a test message
    success = rabbitmq_manager.send_message(
        "ex.sim.result", "test.key", "Hello, World!")

    # Verify success and proper method calls
    assert success is True
    mocked_channel.basic_publish.assert_called_once_with(
        exchange="ex.sim.result",
        routing_key="test.key",
        body="Hello, World!",
        properties=mock.ANY
    )


def test_send_message_with_properties(rabbitmq_manager, mock_connection):
    """Test sending a message with custom properties."""
    _, mocked_channel = mock_connection

    # Create custom properties
    properties = BasicProperties(
        content_type="application/json",
        delivery_mode=1
    )

    # Send message with properties
    success = rabbitmq_manager.send_message(
        "ex.sim.result",
        "test.key",
        "Hello, JSON!",
        properties
    )

    # Verify success and proper method calls with properties
    assert success is True
    mocked_channel.basic_publish.assert_called_once_with(
        exchange="ex.sim.result",
        routing_key="test.key",
        body="Hello, JSON!",
        properties=properties
    )


def test_send_message_general_exception(rabbitmq_manager, mock_connection):
    """Test message sending failure with general exception."""
    _, mocked_channel = mock_connection

    # Force an error during message publishing
    mocked_channel.basic_publish.side_effect = Exception("Publish failed")

    # Test sending with forced failure
    success = rabbitmq_manager.send_message(
        "ex.sim.result", "test.key", "Hello, World!")

    # Verify send_message returns False on failure
    assert success is False
    mocked_channel.basic_publish.assert_called_once()


def test_send_message_amqp_error(rabbitmq_manager, mock_connection):
    """Test that send_message returns False when basic_publish raises AMQPError."""
    _, mocked_channel = mock_connection

    # Simulate AMQP error during publish
    mocked_channel.basic_publish.side_effect = AMQPError("publish failed")

    # Send message that should fail with AMQP error
    success = rabbitmq_manager.send_message("ex.sim.result", "key", "body")

    # Verify failure
    assert success is False


def test_send_result(rabbitmq_manager, mock_connection):
    """Test sending a result message with proper formatting."""
    _, mocked_channel = mock_connection

    # Test data to send
    result_data = {"key": "value"}

    # Send result
    success = rabbitmq_manager.send_result("destination_key", result_data)

    # Verify success
    assert success is True

    # Verify publish was called with correct parameters
    mocked_channel.basic_publish.assert_called_once()
    args, kwargs = mocked_channel.basic_publish.call_args

    # Check exchange and routing key
    assert kwargs["exchange"] == "ex.sim.result"
    assert kwargs["routing_key"] == f"{
        rabbitmq_manager.agent_id}.result.destination_key"

    # Verify serialized data contains expected values
    assert "key: value" in kwargs["body"]


def test_send_result_failure(rabbitmq_manager, monkeypatch):
    """Test that send_result returns False if send_message fails."""
    # Force send_message to return False
    monkeypatch.setattr(
        rabbitmq_manager,
        "send_message",
        lambda *args,
        **kwargs: False)

    # Call send_result
    result = rabbitmq_manager.send_result("dest", {"foo": "bar"})

    # Verify failure propagation
    assert result is False


def test_close_normal(rabbitmq_manager, mock_connection):
    """Test normal connection closure."""
    _, mocked_channel = mock_connection

    # Close connection
    rabbitmq_manager.close()

    # Verify proper cleanup
    mocked_channel.stop_consuming.assert_called_once()
    rabbitmq_manager.connection.close.assert_called_once()


def test_close_with_exception(rabbitmq_manager, mock_connection):
    """Test connection closure with exception handling."""
    _, mocked_channel = mock_connection

    # Simulate exception during stop_consuming
    mocked_channel.stop_consuming.side_effect = pika.exceptions.AMQPError(
        "Close error")

    # Close should handle the exception without raising
    rabbitmq_manager.close()

    # Verify methods were still called
    mocked_channel.stop_consuming.assert_called_once()
    rabbitmq_manager.connection.close.assert_called_once()


def test_connect_failure(mock_connection, mock_config, agent_id):
    """Test connection failure handling causes system exit."""
    mocked_connection, _ = mock_connection

    # Force connection failure
    mocked_connection.side_effect = pika.exceptions.AMQPConnectionError(
        "Connection failed")

    # Attempt to create manager should cause system exit
    with pytest.raises(SystemExit):
        RabbitMQManager(agent_id, mock_config)


def test_setup_infrastructure_channel_closed_by_broker(
        mock_connection, mock_config, agent_id):
    """Test that ChannelClosedByBroker in setup_infrastructure causes system exit."""
    _, mocked_channel = mock_connection

    # Simulate broker closing channel during setup
    mocked_channel.exchange_declare.side_effect = ChannelClosedByBroker(
        406, "PRECONDITION_FAILED")

    # Attempt to create manager should cause system exit
    with pytest.raises(SystemExit):
        RabbitMQManager(agent_id, mock_config)


def test_start_consuming_keyboard_interrupt(rabbitmq_manager, mock_connection):
    """Test message consumption gracefully handling keyboard interrupt."""
    _, mocked_channel = mock_connection

    def mock_handler(*args):
        pass

    # Register handler
    rabbitmq_manager.register_message_handler(mock_handler)

    # Simulate keyboard interrupt during consumption
    mocked_channel.start_consuming.side_effect = KeyboardInterrupt

    # Start consuming should handle KeyboardInterrupt gracefully
    rabbitmq_manager.start_consuming()

    # Verify consumption was stopped
    mocked_channel.stop_consuming.assert_called_once()


def test_start_consuming_amqp_error(rabbitmq_manager, mock_connection):
    """Test error handling during message consumption with AMQP error."""
    _, mocked_channel = mock_connection

    def mock_handler(*args):
        pass

    # Register handler
    rabbitmq_manager.register_message_handler(mock_handler)

    # Simulate AMQP error during consumption
    mocked_channel.start_consuming.side_effect = pika.exceptions.AMQPError(
        "Error")

    # Start consuming should handle AMQPError gracefully
    rabbitmq_manager.start_consuming()

    # Verify cleanup was performed
    mocked_channel.stop_consuming.assert_called_once()
    rabbitmq_manager.connection.close.assert_called_once()
