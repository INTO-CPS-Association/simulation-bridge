import pytest
from typing import Any, Dict, Callable
from unittest.mock import MagicMock

from src.comm.connect import Connect
from src.comm.interfaces import IMessageBroker, IMessageHandler


@pytest.fixture(scope="function")
def config_dict() -> Dict[str, Any]:
    """
    Provides a basic configuration dictionary for Connect.
    """
    return {
        "exchanges": {"output": "test.exchange"},
        "simulation": {"path": None}  # Added path_simulation
    }


@pytest.fixture(scope="function")
def agent_id() -> str:
    """
    Provides a sample agent identifier.
    """
    return "agent123"


@pytest.fixture(scope="function")
def mock_rabbitmq_manager(monkeypatch):
    """
    Patch RabbitMQManager and return its mock.
    """
    mock_manager = MagicMock(spec=IMessageBroker)
    # Ensure connect returns True by default
    mock_manager.connect.return_value = True
    mock_manager.channel = MagicMock()
    mock_manager.channel.is_open = True
    monkeypatch.setattr("src.comm.connect.RabbitMQManager",
                        lambda agent_id, config: mock_manager)
    return mock_manager


@pytest.fixture(scope="function")
def mock_message_handler(monkeypatch, mock_rabbitmq_manager):
    """
    Patch MessageHandler and return its mock.
    """
    mock_handler = MagicMock(spec=IMessageHandler)
    # Handler must have handle_message and set_simulation_handler
    mock_handler.handle_message = MagicMock()
    mock_handler.set_simulation_handler = MagicMock()

    # Fix: Explicitly match the MessageHandler constructor signature with
    # three parameters
    monkeypatch.setattr(
        "src.comm.connect.MessageHandler",
        lambda agent_id, broker, path_simulation=None: mock_handler
    )
    return mock_handler


class TestConnectInitialization:
    """
    Tests for the Connect class initialization and broker selection.
    """

    def test_default_broker_initialization(self,
                                           agent_id,
                                           config_dict,
                                           mock_rabbitmq_manager,
                                           mock_message_handler):
        """
        Ensure Connect initializes RabbitMQManager and MessageHandler by default.
        """
        conn = Connect(agent_id, config_dict)
        assert conn.broker is mock_rabbitmq_manager
        assert conn.message_handler is mock_message_handler

    def test_unsupported_broker_type(self, agent_id, config_dict):
        """
        Passing an unsupported broker_type should raise ValueError.
        """
        with pytest.raises(ValueError):
            Connect(agent_id, config_dict, broker_type="kafka")


class TestConnectMethods:
    """
    Tests for Connect methods: connect, setup, register, start, send, result, close.
    """

    @pytest.fixture(autouse=True)
    def setup_connect(self,
                      agent_id,
                      config_dict,
                      mock_rabbitmq_manager,
                      mock_message_handler):
        """
        Set up a Connect instance for each test.
        """
        self.conn = Connect(agent_id, config_dict)
        yield

    def test_connect_calls_broker_connect(self, mock_rabbitmq_manager):
        """
        connect() should invoke broker.connect().
        """
        self.conn.connect()
        mock_rabbitmq_manager.connect.assert_called_once()

    def test_setup_calls_infrastructure(self, mock_rabbitmq_manager):
        """
        setup() should call setup_infrastructure() on broker.
        """
        self.conn.setup()
        mock_rabbitmq_manager.setup_infrastructure.assert_called_once()

    def test_register_default_handler(
            self, mock_rabbitmq_manager, mock_message_handler):
        """
        register_message_handler() without args uses default handler.
        """
        self.conn.register_message_handler()
        mock_rabbitmq_manager.register_message_handler.assert_called_once_with(
            mock_message_handler.handle_message)

    def test_register_custom_handler(self, mock_rabbitmq_manager):
        """
        register_message_handler() with custom callable.
        """
        custom_handler = lambda *args: None  # pylint: disable=unnecessary-lambda-assignment
        self.conn.register_message_handler(custom_handler)
        mock_rabbitmq_manager.register_message_handler.assert_called_once_with(
            custom_handler)

    def test_start_consuming_channel_active(self, mock_rabbitmq_manager):
        """
        start_consuming() when channel open should call broker.start_consuming().
        """
        self.conn.start_consuming()
        mock_rabbitmq_manager.start_consuming.assert_called_once()

    def test_start_consuming_reconnect_on_closed_channel(self,
                                                         mock_rabbitmq_manager):
        """
        If channel closed, start_consuming tries reconnect then abort on failure.
        """
        mock_rabbitmq_manager.channel.is_open = False
        mock_rabbitmq_manager.connect.return_value = False

        # Should not raise, but not call start_consuming
        self.conn.start_consuming()
        mock_rabbitmq_manager.connect.assert_called()
        mock_rabbitmq_manager.start_consuming.assert_not_called()

    def test_send_message_rabbitmq(self, mock_rabbitmq_manager, config_dict):
        """
        send_message() should delegate to broker.send_message with exchange/routing.
        """
        sent = self.conn.send_message(
            destination="dest",
            message="hello",
            exchange="ex",
            routing_key="rk",
        )
        assert sent is mock_rabbitmq_manager.send_message.return_value
        mock_rabbitmq_manager.send_message.assert_called_once_with(
            "ex", "rk", "hello", None)

    def test_send_message_defaults(self, mock_rabbitmq_manager, config_dict):
        """
        send_message() uses config.exchange and agent_id.dest as routing key.
        """
        sent = self.conn.send_message("dest", "msg")
        assert sent is mock_rabbitmq_manager.send_message.return_value
        mock_rabbitmq_manager.send_message.assert_called_once_with(
            config_dict["exchanges"]["output"],
            f"{self.conn.agent_id}.dest",
            "msg",
            None,
        )

    def test_send_result(self, mock_rabbitmq_manager):
        """
        send_result() delegates to broker.send_result.
        """
        res = self.conn.send_result("x", {"a": 1})
        assert res is mock_rabbitmq_manager.send_result.return_value
        mock_rabbitmq_manager.send_result.assert_called_once_with("x", {"a": 1})

    def test_close_calls_broker_close(self, mock_rabbitmq_manager):
        """
        close() should call broker.close().
        """
        self.conn.close()
        mock_rabbitmq_manager.close.assert_called_once()

    def test_get_and_set_message_handler(self, mock_message_handler):
        """
        get_message_handler() and set_simulation_handler() should work.
        """
        # get
        handler = self.conn.get_message_handler()
        assert handler is mock_message_handler

        # set
        callback = lambda *args: None  # pylint: disable=unnecessary-lambda-assignment
        self.conn.set_simulation_handler(callback)
        mock_message_handler.set_simulation_handler.assert_called_once_with(
            callback)
