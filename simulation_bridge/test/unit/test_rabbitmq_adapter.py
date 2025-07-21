"""Test suite for rabbitmq_adapter.py using pytest and unittest.mock."""

# pylint: disable=redefined-outer-name,unused-argument,protected-access

from unittest import mock
import ssl
import json
import threading
import pytest

from simulation_bridge.src.protocol_adapters.rabbitmq import rabbitmq_adapter


@pytest.fixture
def config_manager_mock(dummy_credentials):
    """Mock ConfigManager to return RabbitMQ configuration."""
    mock_cfg = mock.MagicMock()
    mock_cfg.get_rabbitmq_config.return_value = {
        "username": dummy_credentials["user"]["username"],
        "password": dummy_credentials["user"]["password"],
        "host": "localhost",
        "port": 5672,
        "vhost": "/",
        "infrastructure": {
            "queues": [{"name": "Q.bridge.input"}, {"name": "Q.bridge.result"}]
        },
    }
    return mock_cfg


@pytest.fixture
def pika_connection_mock(monkeypatch):
    mock_channel = mock.MagicMock()
    mock_conn = mock.MagicMock()
    mock_conn.channel.return_value = mock_channel
    monkeypatch.setattr(
        rabbitmq_adapter.pika,
        "BlockingConnection",
        lambda _: mock_conn)
    monkeypatch.setattr(
        rabbitmq_adapter.pika,
        "PlainCredentials",
        lambda *_: None)
    monkeypatch.setattr(
        rabbitmq_adapter.pika,
        "ConnectionParameters",
        lambda **_: None)
    return mock_conn, mock_channel


class TestRabbitMQAdapterInit:
    def test_init_subscribes_to_configured_queues(
            self, config_manager_mock, pika_connection_mock):
        _conn, chan = pika_connection_mock
        rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)
        assert chan.basic_consume.call_count == 2
        queues = [c.kwargs["queue"] for c in chan.basic_consume.call_args_list]
        assert set(queues) == {"Q.bridge.input", "Q.bridge.result"}

    def test_init_emits_some_debug_log(
            self, config_manager_mock, pika_connection_mock):
        with mock.patch.object(rabbitmq_adapter.logger, "debug") as log_debug:
            rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)
            assert log_debug.called


class TestProcessMessage:
    """Tests for RabbitMQAdapter's _process_message method."""
    @pytest.fixture
    def adapter(self, config_manager_mock, pika_connection_mock):
        return rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)

    def test_process_message_yaml_success(self, adapter):
        ch = mock.MagicMock()
        method = mock.MagicMock()
        body = b"simulation:\n  client_id: test\n  simulator: sim"
        adapter._process_message(ch, method, None, body, "Q.bridge.input")
        ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)

    def test_process_message_json_success(self, adapter):
        ch = mock.MagicMock()
        method = mock.MagicMock()
        body = json.dumps(
            {"simulation": {"client_id": "c", "simulator": "s"}}).encode()
        adapter._process_message(ch, method, None, body, "Q.bridge.input")
        ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)

    def test_process_message_raw_fallback(self, adapter):
        ch = mock.MagicMock()
        method = mock.MagicMock()
        body = b"not: valid: yaml"
        adapter._process_message(ch, method, None, body, "Q.bridge.input")
        ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)

    def test_process_message_non_dict_now_acks(self, adapter):
        ch = mock.MagicMock()
        method = mock.MagicMock()
        body = b"[]"
        adapter._process_message(ch, method, None, body, "Q.bridge.input")
        ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)
        ch.basic_nack.assert_not_called()

    def test_process_message_bridge_meta_malformed_json_logs_warning(
            self, adapter):
        ch = mock.MagicMock()
        method = mock.MagicMock()
        msg = {"simulation": {}, "bridge_meta": "{not:json}"}
        body = json.dumps(msg).encode()
        with mock.patch.object(rabbitmq_adapter.logger, "warning") as warn:
            adapter._process_message(ch, method, None, body, "Q.bridge.result")
            ch.basic_ack.assert_called_once_with(
                delivery_tag=method.delivery_tag)
            warn.assert_called_once()


class TestRunConsumer:
    """Tests for the _run_consumer method of RabbitMQAdapter."""
    @pytest.fixture
    def adapter(self, config_manager_mock, pika_connection_mock):
        return rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)

    def test_run_consumer_executes_start_consuming(self, adapter):
        adapter.channel.start_consuming = mock.MagicMock()
        adapter._run_consumer()
        adapter.channel.start_consuming.assert_called_once()

    def test_run_consumer_logs_error(self, adapter):
        adapter._running = True
        adapter.channel.start_consuming = mock.Mock(
            side_effect=RuntimeError("fail"))
        with mock.patch.object(rabbitmq_adapter.logger, "error") as err:
            adapter._run_consumer()
            err.assert_called_once()


class TestStartStopAdapter:
    """Tests for start and stop methods of RabbitMQAdapter."""
    @pytest.fixture
    def adapter(self, config_manager_mock, pika_connection_mock):
        return rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)

    def test_start_creates_thread(self, adapter):
        with mock.patch("threading.Thread") as thread_cls:
            inst = mock.Mock()
            thread_cls.return_value = inst
            adapter.start()
            thread_cls.assert_called_once()
            inst.start.assert_called_once()

    def test_start_raises_on_thread_error(self, adapter):
        with mock.patch("threading.Thread", side_effect=RuntimeError("fail")), \
                mock.patch.object(adapter, "stop") as stop_mock:
            with pytest.raises(RuntimeError):
                adapter.start()
            stop_mock.assert_not_called()

    def test_stop_closes_resources(self, adapter):
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

    def test_stop_raises_when_internal_errors(self, adapter):
        adapter.channel = mock.Mock(is_open=True)
        adapter.connection = mock.Mock(is_open=True)
        adapter.connection.add_callback_threadsafe = mock.Mock(
            side_effect=Exception("fail"))
        with pytest.raises(Exception):
            adapter.stop()


class TestConnectionErrors:
    def test_init_amqp_connection_error(self, config_manager_mock):
        with mock.patch.object(rabbitmq_adapter.pika, "PlainCredentials"), \
            mock.patch.object(rabbitmq_adapter.pika, "ConnectionParameters"), \
            mock.patch.object(
            rabbitmq_adapter.pika,
            "BlockingConnection",
            side_effect=rabbitmq_adapter.pika.exceptions.AMQPConnectionError(
                "fail")
        ):
            with pytest.raises(rabbitmq_adapter.pika.exceptions.AMQPConnectionError):
                rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)

    def test_init_ssl_error(self, config_manager_mock):
        with mock.patch.object(rabbitmq_adapter.pika, "PlainCredentials"), \
            mock.patch.object(rabbitmq_adapter.pika, "ConnectionParameters"), \
            mock.patch.object(
            rabbitmq_adapter.pika,
            "BlockingConnection",
            side_effect=ssl.SSLError("SSL error")
        ):
            with pytest.raises(ssl.SSLError):
                rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)

    def test_init_unexpected_error(self, config_manager_mock):
        with mock.patch.object(rabbitmq_adapter.pika, "PlainCredentials"), \
            mock.patch.object(rabbitmq_adapter.pika, "ConnectionParameters"), \
            mock.patch.object(
            rabbitmq_adapter.pika,
            "BlockingConnection",
            side_effect=ValueError("boom")
        ):
            with pytest.raises(ValueError):
                rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)


class TestTLSConfiguration:
    """Tests for TLS configuration scenarios."""

    @pytest.fixture
    def tls_config_manager_mock(self, dummy_credentials):
        """Mock config manager with TLS enabled."""
        mock_cfg = mock.MagicMock()
        mock_cfg.get_rabbitmq_config.return_value = {
            "username": dummy_credentials["user"]["username"],
            "password": dummy_credentials["user"]["password"],
            "host": "secure.rabbitmq.com",
            "port": 5671,
            "vhost": "/",
            "tls": True,
            "infrastructure": {"queues": [{"name": "Q.bridge.input"}]},
        }
        return mock_cfg

    def test_tls_connection_parameters(
            self, tls_config_manager_mock, dummy_credentials):
        """Test that TLS connection parameters are set correctly."""
        mock_channel = mock.MagicMock()
        mock_conn = mock.MagicMock()
        mock_conn.channel.return_value = mock_channel

        with mock.patch.object(rabbitmq_adapter.pika,
                               "PlainCredentials") as creds_mock, \
            mock.patch.object(rabbitmq_adapter.pika,
                              "ConnectionParameters") as params_mock, \
            mock.patch.object(rabbitmq_adapter.pika,
                              "BlockingConnection", return_value=mock_conn), \
            mock.patch.object(rabbitmq_adapter.ssl,
                              "create_default_context") as ssl_context_mock, \
            mock.patch.object(rabbitmq_adapter.pika,
                              "SSLOptions") as ssl_options_mock:

            rabbitmq_adapter.RabbitMQAdapter(tls_config_manager_mock)

            # Verify SSL context and options were created
            ssl_context_mock.assert_called_once()
            ssl_options_mock.assert_called_once_with(
                ssl_context_mock.return_value, "secure.rabbitmq.com")
            creds_mock.assert_called_once_with(
                dummy_credentials["user"]["username"], dummy_credentials["user"]["password"]
            )

            # Verify connection parameters included SSL options
            params_mock.assert_called_once()
            call_kwargs = params_mock.call_args[1]
            assert "ssl_options" in call_kwargs


class TestMessageProcessingAdvanced:
    """Advanced tests for message processing scenarios."""

    @pytest.fixture
    def adapter(self, config_manager_mock, pika_connection_mock):
        """Instantiate RabbitMQAdapter for tests."""
        return rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)

    # pylint: disable=too-many-statements
    def test_process_message_bridge_result_with_different_protocols(
            self, adapter):
        """Test processing bridge result messages with different protocol types."""
        ch = mock.MagicMock()
        method = mock.MagicMock()

        protocols = ["rest", "mqtt", "rabbitmq", "inmemory", "unknown"]
        for proto in protocols:
            msg = {
                "request_id": "test-123",
                "bridge_meta": {"protocol": proto},
                "destinations": ["client1"],
                "source": "simulator",
            }
            body = json.dumps(msg).encode()
            adapter._process_message(ch, method, None, body, "Q.bridge.result")
            ch.basic_ack.assert_called_with(delivery_tag=method.delivery_tag)
            ch.reset_mock()

    def test_process_message_bridge_meta_valid_json_string(self, adapter):
        """Test processing message with bridge_meta as valid JSON string."""
        ch = mock.MagicMock()
        method = mock.MagicMock()
        msg = {
            "request_id": "test-123",
            "bridge_meta": '{"protocol": "rest", "timestamp": 123456}',
            "destinations": ["client1"],
            "source": "simulator",
        }
        body = json.dumps(msg).encode()
        adapter._process_message(ch, method, None, body, "Q.bridge.result")
        ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)

    def test_process_message_unknown_queue_raises_error(self, adapter):
        """Test processing message from unknown queue raises ValueError."""
        ch = mock.MagicMock()
        method = mock.MagicMock()
        msg = {"some": "data"}
        body = json.dumps(msg).encode()

        with mock.patch.object(rabbitmq_adapter.logger, "error") as log_error:
            adapter._process_message(ch, method, None, body, "Q.unknown.queue")
            ch.basic_nack.assert_called_once_with(
                delivery_tag=method.delivery_tag, requeue=False)
            log_error.assert_called_once()

    def test_process_message_with_empty_destinations(self, adapter):
        """Test processing bridge result message with empty destinations."""
        ch = mock.MagicMock()
        method = mock.MagicMock()
        msg = {
            "request_id": "test-123",
            "bridge_meta": {"protocol": "rest"},
            "destinations": [],
            "source": "simulator",
        }
        body = json.dumps(msg).encode()
        adapter._process_message(ch, method, None, body, "Q.bridge.result")
        ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)


class TestGetConfig:
    """Tests for _get_config method."""

    def test_get_config_returns_rabbitmq_config(
        self, config_manager_mock, pika_connection_mock, dummy_credentials
    ):
        """Test that _get_config returns the RabbitMQ configuration."""
        adapter = rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)
        config = adapter._get_config()

        expected_config = {
            "username": dummy_credentials["user"]["username"],
            "password": dummy_credentials["user"]["password"],
            "host": "localhost",
            "port": 5672,
            "vhost": "/",
            "infrastructure": {
                "queues": [{"name": "Q.bridge.input"}, {"name": "Q.bridge.result"}]
            },
        }
        assert config == expected_config
        config_manager_mock.get_rabbitmq_config.assert_called()


class TestQueueSubscription:
    """Tests for queue subscription logic."""

    def test_init_with_empty_queues_list(
            self, config_manager_mock, dummy_credentials):
        """Test initialization with empty queues list."""
        config_manager_mock.get_rabbitmq_config.return_value = {
            "username": dummy_credentials["user"]["username"],
            "password": dummy_credentials["user"]["password"],
            "host": "localhost",
            "port": 5672,
            "vhost": "/",
            "infrastructure": {"queues": []},
        }

        mock_channel = mock.MagicMock()
        mock_conn = mock.MagicMock()
        mock_conn.channel.return_value = mock_channel

        with mock.patch.object(rabbitmq_adapter.pika, "PlainCredentials"), \
                mock.patch.object(rabbitmq_adapter.pika, "ConnectionParameters"), \
                mock.patch.object(rabbitmq_adapter.pika, "BlockingConnection", return_value=mock_conn):  # pylint: disable=line-too-long

            rabbitmq_adapter.RabbitMQAdapter(
                config_manager_mock)  # pylint: disable=unused-variable
            mock_channel.basic_consume.assert_not_called()

    def test_init_with_queue_without_name(
            self, config_manager_mock, dummy_credentials):
        """Test initialization with queue configuration missing name."""
        config_manager_mock.get_rabbitmq_config.return_value = {
            "username": dummy_credentials["user"]["username"],
            "password": dummy_credentials["user"]["password"],
            "host": "localhost",
            "port": 5672,
            "vhost": "/",
            "infrastructure": {
                "queues": [{"type": "input"}, {"name": "Q.bridge.result"}]
            },
        }

        mock_channel = mock.MagicMock()
        mock_conn = mock.MagicMock()
        mock_conn.channel.return_value = mock_channel

        with mock.patch.object(rabbitmq_adapter.pika, "PlainCredentials"), \
                mock.patch.object(rabbitmq_adapter.pika, "ConnectionParameters"), \
                mock.patch.object(rabbitmq_adapter.pika, "BlockingConnection", return_value=mock_conn):  # pylint: disable=line-too-long

            rabbitmq_adapter.RabbitMQAdapter(
                config_manager_mock)  # pylint: disable=unused-variable
            # Should only subscribe to the queue with name
            mock_channel.basic_consume.assert_called_once()


class TestStopFromConsumerThread:
    """Test stop method when called from consumer thread."""

    @pytest.fixture
    def adapter(self, config_manager_mock, pika_connection_mock):
        """Adapter instance for stop tests."""
        return rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)

    def test_stop_from_consumer_thread_returns_early(self, adapter):
        """Test that stop returns early when called from consumer thread."""
        adapter._running = True
        adapter._consumer_thread = threading.current_thread()

        # Mock the connection methods to verify they're not called
        adapter.connection.add_callback_threadsafe = mock.Mock()
        adapter.connection.close = mock.Mock()

        adapter.stop()

        adapter.connection.add_callback_threadsafe.assert_not_called()
        adapter.connection.close.assert_not_called()


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
                None, None, None, msg, "Q.bridge.input")

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
