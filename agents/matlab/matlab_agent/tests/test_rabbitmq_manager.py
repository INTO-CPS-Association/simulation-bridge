import pytest
from pika import exceptions as pika_exceptions
from unittest import mock
from unittest.mock import MagicMock
from typing import Any, Dict, Tuple

from src.comm.rabbitmq.rabbitmq_manager import RabbitMQManager


@pytest.fixture(scope="function")
def mock_config() -> dict:
    return {
        "rabbitmq": {
            "host": "localhost",
            "port": 5672,
            "username": "guest",
            "password": "guest",
            "heartbeat": 600,
        },
        "exchanges": {
            "input": "ex.bridge.output",
            "output": "ex.sim.result",
        },
        "queue": {
            "durable": True,
            "prefetch_count": 1,
        },
    }


@pytest.fixture(scope="function")
def agent_id() -> str:
    return "test_agent"


@pytest.fixture(scope="function")
def mock_connection(
    mock_config: dict,
):
    connection_path = "src.comm.rabbitmq.rabbitmq_manager.pika.BlockingConnection"
    with mock.patch(connection_path) as connection_mock:
        channel_mock = MagicMock()
        channel_mock.is_open = True  # importante per close()
        connection_mock.return_value.channel.return_value = channel_mock
        yield connection_mock, channel_mock


@pytest.fixture(scope="function")
def rabbitmq_manager(mock_connection, mock_config, agent_id) -> RabbitMQManager:
    manager = RabbitMQManager(agent_id, mock_config)
    manager.connect()
    manager.setup_infrastructure()
    return manager


class TestRabbitMQManager:

    def test_initialization(self, mock_connection, mock_config, agent_id):
        connection_mock, channel_mock = mock_connection
        manager = RabbitMQManager(agent_id, mock_config)
        manager.connect()
        manager.setup_infrastructure()

        connection_mock.assert_called_once()
        channel_mock.exchange_declare.assert_any_call(
            exchange=mock_config["exchanges"]["input"],
            exchange_type="topic",
            durable=True,
        )

        channel_mock.exchange_declare.assert_any_call(
            exchange=mock_config["exchanges"]["output"],
            exchange_type="topic",
            durable=True,
        )
        queue_name = f"Q.sim.{agent_id}"
        channel_mock.queue_declare.assert_called_once_with(
            queue=queue_name,
            durable=mock_config["queue"]["durable"],
        )
        channel_mock.queue_bind.assert_called_once_with(
            exchange=mock_config["exchanges"]["input"],
            queue=queue_name,
            routing_key=f"*.{agent_id}",
        )
        channel_mock.basic_qos.assert_called_once_with(
            prefetch_count=mock_config["queue"]["prefetch_count"],
        )

    def test_register_message_handler(self, rabbitmq_manager):
        def handler(channel, method, properties, body):
            pass
        rabbitmq_manager.register_message_handler(handler)
        assert rabbitmq_manager.message_handler is handler

    @pytest.mark.parametrize("with_handler, expect_consume", [(True, True), (False, False)])
    def test_start_consuming(self, rabbitmq_manager, mock_connection, with_handler, expect_consume):
        _, channel_mock = mock_connection
        if with_handler:
            rabbitmq_manager.register_message_handler(lambda *args: None)

        rabbitmq_manager.start_consuming()

        if expect_consume:
            channel_mock.basic_consume.assert_called_once()
            channel_mock.start_consuming.assert_called_once()
        else:
            channel_mock.basic_consume.assert_not_called()
            channel_mock.start_consuming.assert_not_called()

    def test_send_message_success_and_failure(
        self,
        rabbitmq_manager: RabbitMQManager,
        mock_connection: Tuple[mock._patch, MagicMock],
        mock_config: Dict[str, Any],  # <-- aggiungi qui
    ) -> None:
        _, channel_mock = mock_connection

        # Success
        result_ok = rabbitmq_manager.send_message(
            mock_config["exchanges"]["output"],
            "routing.key",
            "body",
        )
        assert result_ok is True
        channel_mock.basic_publish.assert_called_once()

        # AMQPError
        channel_mock.basic_publish.reset_mock()
        channel_mock.basic_publish.side_effect = pika_exceptions.AMQPError()
        result_amqp = rabbitmq_manager.send_message(
            mock_config["exchanges"]["output"], "key", "body"
        )
        assert result_amqp is False

        # General Exception
        channel_mock.basic_publish.reset_mock()
        channel_mock.basic_publish.side_effect = Exception()
        result_exc = rabbitmq_manager.send_message(
            mock_config["exchanges"]["output"], "key", "body"
        )
        assert result_exc is False

    def test_send_result_and_propagation_failure(self, rabbitmq_manager, mock_connection, monkeypatch):
        _, channel_mock = mock_connection

        payload = {"key": "value"}
        succeeded = rabbitmq_manager.send_result("dest", payload)
        assert succeeded is True
        _, kwargs = channel_mock.basic_publish.call_args
        assert "ex.sim.result" == kwargs["exchange"]
        assert ".result.dest" in kwargs["routing_key"]
        assert "key: value" in kwargs["body"]

        # Force send_message failure
        monkeypatch.setattr(rabbitmq_manager, "send_message", lambda *args, **kwargs: False)
        failed = rabbitmq_manager.send_result("dest", payload)
        assert failed is False

    def test_close_methods(self, rabbitmq_manager, mock_connection):
        _, channel_mock = mock_connection

        # Normal close
        rabbitmq_manager.close()
        channel_mock.stop_consuming.assert_called_once()
        rabbitmq_manager.connection.close.assert_called_once()

        # Exception in stop_consuming
        channel_mock.stop_consuming.reset_mock()
        channel_mock.stop_consuming.side_effect = pika_exceptions.AMQPError()
        rabbitmq_manager.close()
        channel_mock.stop_consuming.assert_called_once()

    def test_connect_and_setup_failures(self, mock_connection, mock_config, agent_id):
        connection_mock, channel_mock = mock_connection

        # Simula fallimento connessione, connect() deve fallire e non sys.exit direttamente
        connection_mock.side_effect = pika_exceptions.AMQPConnectionError()
        manager = RabbitMQManager(agent_id, mock_config)
        # connect() ritorna False, quindi fai l'assert
        assert manager.connect() is False

        # Ora simuliamo fallimento in setup_infrastructure che causa sys.exit
        connection_mock.side_effect = None  # Reset side effect
        manager.connect()  # Questa dovrebbe ora funzionare
        channel_mock.exchange_declare.side_effect = pika_exceptions.ChannelClosedByBroker(
            406, "PRECONDITION_FAILED"
        )

        with pytest.raises(SystemExit):
            manager.setup_infrastructure()

    def test_start_consuming_interrupts_and_errors(self, rabbitmq_manager, mock_connection):
        _, channel_mock = mock_connection
        rabbitmq_manager.register_message_handler(lambda *_: None)

        # KeyboardInterrupt stops consuming gracefully
        channel_mock.start_consuming.side_effect = KeyboardInterrupt
        rabbitmq_manager.start_consuming()
        channel_mock.stop_consuming.assert_called_once()

        channel_mock.start_consuming.reset_mock()
        channel_mock.stop_consuming.reset_mock()

        # AMQPError during consuming closes connection
        channel_mock.start_consuming.side_effect = pika_exceptions.AMQPError()
        rabbitmq_manager.start_consuming()
        channel_mock.stop_consuming.assert_called_once()
        rabbitmq_manager.connection.close.assert_called_once()
