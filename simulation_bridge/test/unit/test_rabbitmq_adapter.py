"""Test suite for rabbitmq_adapter.py using pytest and unittest.mock."""

# pylint: disable=redefined-outer-name,unused-argument,protected-access

from unittest import mock

import json
import pytest

from simulation_bridge.src.protocol_adapters.rabbitmq import rabbitmq_adapter


@pytest.fixture
def config_manager_mock(dummy_credentials):
    """Mocked ConfigManager providing RabbitMQ configuration."""
    mock_cfg = mock.MagicMock()
    mock_cfg.get_rabbitmq_config.return_value = {
        'username': dummy_credentials['user']['username'],
        'password': dummy_credentials['user']['password'],
        'host': 'localhost',
        'port': 5672,
        'vhost': '/',
        'infrastructure': {'queues': [{'name': 'Q.bridge.input'}, {'name': 'Q.bridge.result'}]}
    }
    return mock_cfg


@pytest.fixture
def pika_connection_mock(monkeypatch):
    """Patch pika.BlockingConnection and channel for RabbitMQ connection."""
    mock_channel = mock.MagicMock()
    mock_conn = mock.MagicMock()
    mock_conn.channel.return_value = mock_channel

    monkeypatch.setattr(
        rabbitmq_adapter.pika,
        "BlockingConnection",
        lambda params: mock_conn)
    monkeypatch.setattr(
        rabbitmq_adapter.pika,
        "PlainCredentials",
        lambda u,
        p: None)
    monkeypatch.setattr(
        rabbitmq_adapter.pika,
        "ConnectionParameters",
        lambda **kwargs: None)
    return mock_conn, mock_channel


class TestRabbitMQAdapterInit:
    """Tests for RabbitMQAdapter initialization and queue subscription."""

    def test_init_subscribes_to_configured_queues(
            self, config_manager_mock, pika_connection_mock):
        """RabbitMQAdapter should subscribe to queues defined in config."""
        _conn_mock, chan_mock = pika_connection_mock
        adapter = rabbitmq_adapter.RabbitMQAdapter(   # pylint: disable=unused-variable
            config_manager_mock)
        # Should call basic_consume for each queue
        assert chan_mock.basic_consume.call_count == 2
        calls = [call.kwargs['queue']
                 for call in chan_mock.basic_consume.call_args_list]
        assert 'Q.bridge.input' in calls
        assert 'Q.bridge.result' in calls

    def test_init_logger_debug_called(
            self, config_manager_mock, pika_connection_mock):
        """Initialization logs debug messages."""
        with mock.patch.object(rabbitmq_adapter.logger, "debug") as log_debug:
            rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)
            log_debug.assert_any_call("RabbitMQ adapter initialized")
            log_debug.assert_any_call(
                "RabbitMQ adapter initialized and subscribed to queues")


class TestProcessMessage:
    """Tests for the _process_message method handling incoming messages."""

    @pytest.fixture
    def adapter(self, config_manager_mock, pika_connection_mock):
        """Instantiate RabbitMQAdapter for tests."""
        return rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)

    # pylint: disable=protected-access
    def test_process_message_yaml_success(self, adapter):
        """Process YAML message correctly and ack message."""
        ch = mock.MagicMock()
        method = mock.MagicMock()
        body = b"simulation:\n  client_id: test\n  simulator: sim"
        adapter._process_message(ch, method, None, body, 'Q.bridge.input')
        ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)

    def test_process_message_json_success(self, adapter):
        """Process JSON message correctly and ack message."""
        ch = mock.MagicMock()
        method = mock.MagicMock()
        body = json.dumps(
            {"simulation": {"client_id": "client", "simulator": "sim"}}).encode()
        adapter._process_message(ch, method, None, body, 'Q.bridge.input')
        ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)

    def test_process_message_raw_fallback(self, adapter):
        """Process raw message fallback and ack message."""
        ch = mock.MagicMock()
        method = mock.MagicMock()
        # Unparsable YAML/JSON
        body = b"not: valid: yaml"
        adapter._process_message(ch, method, None, body, 'Q.bridge.input')
        ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)

    def test_process_message_non_dict_raises_nack(self, adapter):
        """Non-dict message triggers nack and error log."""
        ch = mock.MagicMock()
        method = mock.MagicMock()
        body = b"[]"
        with mock.patch.object(rabbitmq_adapter.logger, "error") as log_error:
            adapter._process_message(ch, method, None, body, 'Q.bridge.input')
            ch.basic_nack.assert_called_once_with(
                delivery_tag=method.delivery_tag, requeue=False)
            log_error.assert_called_once()

    def test_process_message_bridge_meta_malformed_json_logs_warning(
            self, adapter):
        """Malformed JSON in bridge_meta logs warning but does not raise."""
        ch = mock.MagicMock()
        method = mock.MagicMock()
        msg = {
            "simulation": {},
            "bridge_meta": "{not:json}"
        }
        body = json.dumps(msg).encode()
        with mock.patch.object(rabbitmq_adapter.logger, "warning") as log_warn:
            adapter._process_message(ch, method, None, body, 'Q.bridge.result')
            ch.basic_ack.assert_called_once_with(
                delivery_tag=method.delivery_tag)
            log_warn.assert_called_once()


class TestRunConsumer:
    """Tests for _run_consumer method running the consumer thread."""

    @pytest.fixture
    def adapter(self, config_manager_mock, pika_connection_mock):
        """Adapter instance for consumer tests."""
        return rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)

    # pylint: disable=protected-access
    def test_run_consumer_starts_and_sets_running_flag(self, adapter):
        """_run_consumer sets _running True and calls start_consuming."""
        adapter.channel.start_consuming = mock.MagicMock()
        adapter._run_consumer()
        assert not adapter._running  # Should be False after finishing
        adapter.channel.start_consuming.assert_called_once()

    def test_run_consumer_logs_error_on_exception(self, adapter):
        """Logs error if start_consuming raises exception while running."""
        adapter._running = True
        adapter.channel.start_consuming = mock.Mock(
            side_effect=RuntimeError("fail"))
        with mock.patch.object(rabbitmq_adapter.logger, "error") as log_error:
            adapter._run_consumer()
            log_error.assert_called_once()


class TestStartStopAdapter:
    """Tests for start and stop lifecycle methods of RabbitMQAdapter."""

    @pytest.fixture
    def adapter(self, config_manager_mock, pika_connection_mock):
        """Adapter instance for lifecycle tests."""
        return rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)

    def test_start_creates_and_starts_thread(self, adapter):
        """Start method creates and starts consumer thread."""
        with mock.patch("threading.Thread") as thread_mock:
            thread_inst = mock.Mock()
            thread_mock.return_value = thread_inst
            adapter.start()
            thread_mock.assert_called_once()
            thread_inst.start.assert_called_once()

    def test_start_logs_and_raises_on_exception(self, adapter):
        """Start logs error and raises if thread creation fails."""
        with mock.patch("threading.Thread", side_effect=RuntimeError("fail")), \
                mock.patch.object(rabbitmq_adapter.logger, "error") as log_error, \
                mock.patch.object(adapter, "stop") as stop_mock:
            with pytest.raises(RuntimeError):
                adapter.start()
            log_error.assert_called_once()
            stop_mock.assert_called_once()

    def test_stop_stops_consuming_and_closes_connection(self, adapter):
        """Stop schedules stop_consuming, joins thread and closes connection."""
        adapter._running = True
        adapter.channel.is_open = True
        adapter.connection.is_open = True
        adapter._consumer_thread = mock.Mock(
            is_alive=mock.Mock(return_value=True))
        adapter.connection.add_callback_threadsafe = mock.Mock()
        adapter.connection.close = mock.Mock()

        adapter.stop()

        adapter.connection.add_callback_threadsafe.assert_called_once()
        adapter._consumer_thread.join.assert_called_once_with(timeout=5)
        adapter.connection.close.assert_called_once()

    def test_stop_handles_exceptions_gracefully(self, adapter):
        """Stop method handles exceptions without raising."""
        adapter.channel = mock.Mock(is_open=True)
        adapter.connection = mock.Mock(is_open=True)
        adapter.connection.add_callback_threadsafe = mock.Mock(
            side_effect=Exception("fail"))
        adapter._consumer_thread = mock.Mock()
        adapter._consumer_thread.is_alive = mock.Mock(return_value=True)
        adapter._consumer_thread.join = mock.Mock(side_effect=Exception("fail"))
        adapter.connection.close = mock.Mock(side_effect=Exception("fail"))

        with mock.patch.object(rabbitmq_adapter.logger, "warning") as log_warn, \
                mock.patch.object(rabbitmq_adapter.logger, "error") as log_error:
            adapter.stop()
            assert log_warn.call_count >= 1
            # error log might be called due to add_callback_threadsafe
            assert log_error.call_count >= 1


class TestHandleMessageAndStartAdapter:
    """Tests for _handle_message and _start_adapter methods."""

    @pytest.fixture
    def adapter(self, config_manager_mock, pika_connection_mock):
        """RabbitMQAdapter instance for handle/start adapter tests."""
        return rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)

    # pylint: disable=protected-access
    def test_handle_message_calls_process_message(self, adapter):
        """_handle_message calls _process_message with expected args."""
        with mock.patch.object(adapter, "_process_message") as process_mock:
            msg = {"some": "data"}
            adapter._handle_message(msg)
            process_mock.assert_called_once_with(
                None, None, None, msg, 'Q.bridge.input')

    def test_start_adapter_starts_consuming(self, adapter):
        """_start_adapter calls channel.start_consuming and handles exceptions."""
        adapter.channel.start_consuming = mock.Mock()
        adapter._start_adapter()
        adapter.channel.start_consuming.assert_called_once()

    def test_start_adapter_logs_error_on_exception(self, adapter):
        """_start_adapter logs error and raises if start_consuming fails."""
        adapter.channel.start_consuming = mock.Mock(
            side_effect=RuntimeError("fail"))
        with mock.patch.object(rabbitmq_adapter.logger, "error") as log_error:
            with pytest.raises(RuntimeError):
                adapter._start_adapter()
            log_error.assert_called_once()
