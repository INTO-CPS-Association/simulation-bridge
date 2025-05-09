from unittest import mock
from unittest.mock import MagicMock

import pika
import pytest
from pika import BasicProperties
from pika.exceptions import AMQPError, ChannelClosedByBroker
from src.core.rabbitmq_manager import RabbitMQManager

# Example configuration for tests
MOCK_CONFIG = {
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

AGENT_ID = "test_agent"


@pytest.fixture
def mock_pika_connection():
    """Mock for Pika connection."""
    with mock.patch("src.core.rabbitmq_manager.pika.BlockingConnection") as mocked_connection:
        mocked_channel = MagicMock()
        mocked_connection.return_value.channel.return_value = mocked_channel
        yield mocked_connection, mocked_channel


def test_rabbitmq_manager_initialization(mock_pika_connection):
    """Test RabbitMQManager initialization and connection setup."""
    mocked_connection, mocked_channel = mock_pika_connection
    RabbitMQManager(AGENT_ID, MOCK_CONFIG)

    # Verify Pika methods are called
    mocked_connection.assert_called_once()
    mocked_channel.exchange_declare.assert_any_call(
        exchange="ex.bridge.output", exchange_type="topic", durable=True)
    mocked_channel.exchange_declare.assert_any_call(
        exchange="ex.sim.result", exchange_type="topic", durable=True)
    mocked_channel.queue_declare.assert_called_once_with(
        queue=f"Q.sim.{AGENT_ID}", durable=True)
    mocked_channel.queue_bind.assert_called_once_with(
        exchange="ex.bridge.output",
        queue=f"Q.sim.{AGENT_ID}",
        routing_key=f"*.{AGENT_ID}")
    mocked_channel.basic_qos.assert_called_once_with(prefetch_count=1)


def test_register_message_handler(mock_pika_connection):
    """Test message handler registration."""
    _, mocked_channel = mock_pika_connection
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)

    def mock_handler(*args):
        pass

    manager.register_message_handler(mock_handler)
    assert manager.message_handler == mock_handler


def test_start_consuming(mock_pika_connection):
    """Test starting message consumption."""
    _, mocked_channel = mock_pika_connection
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)

    def mock_handler(*args):
        pass

    manager.register_message_handler(mock_handler)
    manager.start_consuming()

    mocked_channel.basic_consume.assert_called_once_with(
        queue=f"Q.sim.{AGENT_ID}",
        on_message_callback=mock_handler
    )
    mocked_channel.start_consuming.assert_called_once()


def test_send_message_success(mock_pika_connection):
    """Test successful message sending."""
    _, mocked_channel = mock_pika_connection
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)

    success = manager.send_message(
        "ex.sim.result", "test.key", "Hello, World!")
    assert success is True

    mocked_channel.basic_publish.assert_called_once_with(
        exchange="ex.sim.result",
        routing_key="test.key",
        body="Hello, World!",
        properties=mock.ANY
    )


def test_send_message_failure(mock_pika_connection):
    """Test message sending failure."""
    _, mocked_channel = mock_pika_connection

    # Force an error during message publishing
    mocked_channel.basic_publish.side_effect = Exception("Publish failed")

    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)

    # Test: sending a message that should fail
    success = manager.send_message(
        "ex.sim.result", "test.key", "Hello, World!")

    # Verify send_message returns False on failure
    assert success is False
    mocked_channel.basic_publish.assert_called_once()


def test_send_result(mock_pika_connection):
    """Test sending a result message."""
    _, mocked_channel = mock_pika_connection
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)

    result_data = {"key": "value"}
    success = manager.send_result("destination_key", result_data)
    assert success is True

    mocked_channel.basic_publish.assert_called_once()
    args, kwargs = mocked_channel.basic_publish.call_args
    assert kwargs["exchange"] == "ex.sim.result"
    assert kwargs["routing_key"] == f"{AGENT_ID}.result.destination_key"
    # Verify data is serialized correctly
    assert "key: value" in kwargs["body"]


def test_close(mock_pika_connection):
    """Test connection closure."""
    _, mocked_channel = mock_pika_connection
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)

    manager.close()
    mocked_channel.stop_consuming.assert_called_once()
    manager.connection.close.assert_called_once()


def test_connect_failure(mock_pika_connection):
    """Test connection failure handling."""
    mocked_connection, _ = mock_pika_connection
    mocked_connection.side_effect = pika.exceptions.AMQPConnectionError(
        "Connection failed")

    with pytest.raises(SystemExit):
        RabbitMQManager(AGENT_ID, MOCK_CONFIG)


def test_start_consuming_keyboard_interrupt(mock_pika_connection):
    """Test message consumption stop on keyboard interrupt."""
    _, mocked_channel = mock_pika_connection
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)

    def mock_handler(*args):
        pass

    manager.register_message_handler(mock_handler)
    mocked_channel.start_consuming.side_effect = KeyboardInterrupt

    manager.start_consuming()
    mocked_channel.stop_consuming.assert_called_once()


def test_start_consuming_amqp_error(mock_pika_connection):
    """Test error handling during message consumption."""
    _, mocked_channel = mock_pika_connection
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)

    def mock_handler(*args):
        pass

    manager.register_message_handler(mock_handler)
    mocked_channel.start_consuming.side_effect = pika.exceptions.AMQPError(
        "Error")

    manager.start_consuming()
    mocked_channel.stop_consuming.assert_called_once()
    manager.connection.close.assert_called_once()


def test_send_message_with_properties(mock_pika_connection):
    """Test sending a message with custom properties."""
    _, mocked_channel = mock_pika_connection
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)

    properties = BasicProperties(
        content_type="application/json",
        delivery_mode=1)
    success = manager.send_message(
        "ex.sim.result",
        "test.key",
        "Hello, JSON!",
        properties)
    assert success is True

    mocked_channel.basic_publish.assert_called_once_with(
        exchange="ex.sim.result",
        routing_key="test.key",
        body="Hello, JSON!",
        properties=properties
    )


def test_close_with_exception(mock_pika_connection):
    """Test connection closure when an exception occurs."""
    _, mocked_channel = mock_pika_connection
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)

    # Simulate an exception during stop_consuming
    mocked_channel.stop_consuming.side_effect = pika.exceptions.AMQPError(
        "Close error")

    manager.close()
    mocked_channel.stop_consuming.assert_called_once()
    manager.connection.close.assert_called_once()


def test_setup_infrastructure_channel_closed_by_broker(mock_pika_connection):
    """Test che un ChannelClosedByBroker in setup_infrastructure causi sys.exit."""
    _, mocked_channel = mock_pika_connection
    # Simula l'errore sul primo exchange_declare
    mocked_channel.exchange_declare.side_effect = ChannelClosedByBroker(
        406, "PRECONDITION_FAILED")
    with pytest.raises(SystemExit):
        RabbitMQManager(AGENT_ID, MOCK_CONFIG)


def test_start_consuming_without_handler(mock_pika_connection):
    """Test che start_consuming senza handler non chiami basic_consume né start_consuming."""
    _, mocked_channel = mock_pika_connection
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)
    # Non registro nessun handler
    manager.start_consuming()
    mocked_channel.basic_consume.assert_not_called()
    mocked_channel.start_consuming.assert_not_called()


def test_send_message_amqp_error(mock_pika_connection):
    """Test che send_message ritorni False quando basic_publish solleva AMQPError."""
    _, mocked_channel = mock_pika_connection
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)
    mocked_channel.basic_publish.side_effect = AMQPError("publish failed")
    success = manager.send_message("ex.sim.result", "key", "body")
    assert success is False


def test_send_result_failure(monkeypatch, mock_pika_connection):
    """Test che send_result ritorni False se send_message fallisce."""
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)
    # Forziamo send_message a ritornare False
    monkeypatch.setattr(manager, "send_message", lambda *args, **kwargs: False)
    result = manager.send_result("dest", {"foo": "bar"})
    assert result is False
