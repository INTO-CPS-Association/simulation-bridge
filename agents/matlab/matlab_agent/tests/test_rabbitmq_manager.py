import pytest
from unittest import mock
from unittest.mock import MagicMock
from src.core.rabbitmq_manager import RabbitMQManager
from pika import BasicProperties

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
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)
    
    # Verify Pika methods are called
    mocked_connection.assert_called_once()
    mocked_channel.exchange_declare.assert_any_call(exchange="ex.bridge.output", exchange_type="topic", durable=True)
    mocked_channel.exchange_declare.assert_any_call(exchange="ex.sim.result", exchange_type="topic", durable=True)
    mocked_channel.queue_declare.assert_called_once_with(queue=f"Q.sim.{AGENT_ID}", durable=True)
    mocked_channel.queue_bind.assert_called_once_with(exchange="ex.bridge.output", queue=f"Q.sim.{AGENT_ID}", routing_key=f"*.{AGENT_ID}")
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
    
    success = manager.send_message("ex.sim.result", "test.key", "Hello, World!")
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
    success = manager.send_message("ex.sim.result", "test.key", "Hello, World!")
    
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
    assert "key: value" in kwargs["body"]  # Verify data is serialized correctly


def test_close(mock_pika_connection):
    """Test connection closure."""
    _, mocked_channel = mock_pika_connection
    manager = RabbitMQManager(AGENT_ID, MOCK_CONFIG)
    
    manager.close()
    mocked_channel.stop_consuming.assert_called_once()
    manager.connection.close.assert_called_once()
