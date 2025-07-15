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


class TestConnectionErrors:
    """Tests for connection error handling scenarios."""

    def test_init_amqp_connection_error(self, config_manager_mock):
        """Test initialization with AMQP connection error."""
        with mock.patch.object(rabbitmq_adapter.pika, "PlainCredentials"), \
                mock.patch.object(rabbitmq_adapter.pika, "ConnectionParameters"), \
                mock.patch.object(
                    rabbitmq_adapter.pika,
                    "BlockingConnection", 
                    side_effect=rabbitmq_adapter.pika.exceptions.AMQPConnectionError(
                                      "Connection failed")), \
                mock.patch.object(rabbitmq_adapter.logger, "error") as log_error:
            with pytest.raises(RuntimeError,
                               match="Connection failed. Check TLS settings and port."):
                rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)
            assert log_error.call_count >= 2  # Two error logs expected

    def test_init_ssl_error(self, config_manager_mock):
        """Test initialization with SSL error."""
        with mock.patch.object(rabbitmq_adapter.pika, "PlainCredentials"), \
                mock.patch.object(rabbitmq_adapter.pika, "ConnectionParameters"), \
                mock.patch.object(rabbitmq_adapter.pika, "BlockingConnection",
                                  side_effect=ssl.SSLError("SSL error")), \
                mock.patch.object(rabbitmq_adapter.logger, "error") as log_error:
            with pytest.raises(RuntimeError,
                               match="Connection failed. Check TLS settings and port."):
                rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)
            assert log_error.call_count >= 2

    def test_init_unexpected_error(self, config_manager_mock):
        """Test initialization with unexpected error."""
        with mock.patch.object(rabbitmq_adapter.pika, "PlainCredentials"), \
                mock.patch.object(rabbitmq_adapter.pika, "ConnectionParameters"), \
                mock.patch.object(rabbitmq_adapter.pika, "BlockingConnection",
                                  side_effect=ValueError("Unexpected error")), \
                mock.patch.object(rabbitmq_adapter.logger, "error") as log_error:
            with pytest.raises(ValueError):
                rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)
            log_error.assert_called_once()

    def test_init_with_tls_enabled(self, config_manager_mock):
        """Test initialization with TLS enabled."""
        config_manager_mock.get_rabbitmq_config.return_value = {
            'username': 'user',
            'password': 'pass',
            'host': 'localhost',
            'port': 5671,
            'vhost': '/',
            'tls': True,
            'infrastructure': {'queues': [{'name': 'Q.bridge.input'}]}
        }

        mock_channel = mock.MagicMock()
        mock_conn = mock.MagicMock()
        mock_conn.channel.return_value = mock_channel

        with mock.patch.object(rabbitmq_adapter.pika, "PlainCredentials") as creds_mock, \
                mock.patch.object(
                    rabbitmq_adapter.pika,
                    "ConnectionParameters") as params_mock, \
                mock.patch.object(
                    rabbitmq_adapter.pika,
                    "BlockingConnection", return_value=mock_conn), \
                mock.patch.object(
                    rabbitmq_adapter.ssl,
                    "create_default_context") as ssl_context_mock, \
                mock.patch.object(
                    rabbitmq_adapter.pika,
                    "SSLOptions") as ssl_options_mock:

            adapter = rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)
            creds_mock.assert_called_once_with("user", "pass")
            ssl_context_mock.assert_called_once()
            ssl_options_mock.assert_called_once()
            params_mock.assert_called_once()
            assert adapter.connection == mock_conn


class TestTLSConfiguration:
    """Tests for TLS configuration scenarios."""

    @pytest.fixture
    def tls_config_manager_mock(self):
        """Mock config manager with TLS enabled."""
        mock_cfg = mock.MagicMock()
        mock_cfg.get_rabbitmq_config.return_value = {
            'username': 'user',
            'password': 'pass',
            'host': 'secure.rabbitmq.com',
            'port': 5671,
            'vhost': '/',
            'tls': True,
            'infrastructure': {'queues': [{'name': 'Q.bridge.input'}]}
        }
        return mock_cfg

    def test_tls_connection_parameters(self, tls_config_manager_mock):
        """Test that TLS connection parameters are set correctly."""
        mock_channel = mock.MagicMock()
        mock_conn = mock.MagicMock()
        mock_conn.channel.return_value = mock_channel

        with mock.patch.object(
            rabbitmq_adapter.pika,
            "PlainCredentials") as creds_mock, \
                mock.patch.object(
                    rabbitmq_adapter.pika,
                    "ConnectionParameters") as params_mock, \
                mock.patch.object(
                    rabbitmq_adapter.pika,
                    "BlockingConnection", return_value=mock_conn), \
                mock.patch.object(
                    rabbitmq_adapter.ssl,
                    "create_default_context") as ssl_context_mock, \
                mock.patch.object(
                    rabbitmq_adapter.pika,
                    "SSLOptions") as ssl_options_mock:

            rabbitmq_adapter.RabbitMQAdapter(tls_config_manager_mock)

            # Verify SSL context and options were created
            ssl_context_mock.assert_called_once()
            ssl_options_mock.assert_called_once_with(
                ssl_context_mock.return_value, 'secure.rabbitmq.com')
            creds_mock.assert_called_once_with("user", "pass")

            # Verify connection parameters included SSL options
            params_mock.assert_called_once()
            call_kwargs = params_mock.call_args[1]
            assert 'ssl_options' in call_kwargs


class TestMessageProcessingAdvanced:
    """Advanced tests for message processing scenarios."""

    @pytest.fixture
    def adapter(self, config_manager_mock, pika_connection_mock):
        """Instantiate RabbitMQAdapter for tests."""
        return rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)

    def test_process_message_bridge_result_with_different_protocols(
            self, adapter):
        """Test processing bridge result messages with different protocol types."""
        ch = mock.MagicMock()
        method = mock.MagicMock()

        # Test REST protocol
        msg = {
            "request_id": "test-123",
            "bridge_meta": {"protocol": "rest"},
            "destinations": ["client1"],
            "source": "simulator"
        }
        body = json.dumps(msg).encode()
        adapter._process_message(ch, method, None, body, 'Q.bridge.result')
        ch.basic_ack.assert_called_with(delivery_tag=method.delivery_tag)

        # Test MQTT protocol
        ch.reset_mock()
        msg["bridge_meta"]["protocol"] = "mqtt"
        body = json.dumps(msg).encode()
        adapter._process_message(ch, method, None, body, 'Q.bridge.result')
        ch.basic_ack.assert_called_with(delivery_tag=method.delivery_tag)

        # Test RabbitMQ protocol
        ch.reset_mock()
        msg["bridge_meta"]["protocol"] = "rabbitmq"
        body = json.dumps(msg).encode()
        adapter._process_message(ch, method, None, body, 'Q.bridge.result')
        ch.basic_ack.assert_called_with(delivery_tag=method.delivery_tag)

        # Test inmemory protocol
        ch.reset_mock()
        msg["bridge_meta"]["protocol"] = "inmemory"
        body = json.dumps(msg).encode()
        adapter._process_message(ch, method, None, body, 'Q.bridge.result')
        ch.basic_ack.assert_called_with(delivery_tag=method.delivery_tag)

        # Test unknown protocol
        ch.reset_mock()
        msg["bridge_meta"]["protocol"] = "unknown"
        body = json.dumps(msg).encode()
        adapter._process_message(ch, method, None, body, 'Q.bridge.result')
        ch.basic_ack.assert_called_with(delivery_tag=method.delivery_tag)

    def test_process_message_bridge_meta_non_json_string(self, adapter):
        """Test processing message with bridge_meta as non-JSON string."""
        ch = mock.MagicMock()
        method = mock.MagicMock()
        msg = {
            "request_id": "test-123",
            "bridge_meta": "simple string value",
            "destinations": ["client1"],
            "source": "simulator"
        }
        body = json.dumps(msg).encode()

        with mock.patch.object(rabbitmq_adapter.logger, "debug") as log_debug:
            adapter._process_message(ch, method, None, body, 'Q.bridge.result')
            ch.basic_ack.assert_called_once_with(
                delivery_tag=method.delivery_tag)
            log_debug.assert_any_call(
                "bridge_meta is a non-JSON string: %s",
                "simple string value")

    def test_process_message_bridge_meta_valid_json_string(self, adapter):
        """Test processing message with bridge_meta as valid JSON string."""
        ch = mock.MagicMock()
        method = mock.MagicMock()
        msg = {
            "request_id": "test-123",
            "bridge_meta": '{"protocol": "rest", "timestamp": 123456}',
            "destinations": ["client1"],
            "source": "simulator"
        }
        body = json.dumps(msg).encode()
        adapter._process_message(ch, method, None, body, 'Q.bridge.result')
        ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)

    def test_process_message_unknown_queue_raises_error(self, adapter):
        """Test processing message from unknown queue raises ValueError."""
        ch = mock.MagicMock()
        method = mock.MagicMock()
        msg = {"some": "data"}
        body = json.dumps(msg).encode()

        with mock.patch.object(rabbitmq_adapter.logger, "error") as log_error:
            adapter._process_message(ch, method, None, body, 'Q.unknown.queue')
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
            "source": "simulator"
        }
        body = json.dumps(msg).encode()
        adapter._process_message(ch, method, None, body, 'Q.bridge.result')
        ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)


class TestGetConfig:
    """Tests for _get_config method."""

    def test_get_config_returns_rabbitmq_config(
            self, config_manager_mock, pika_connection_mock):
        """Test that _get_config returns the RabbitMQ configuration."""
        adapter = rabbitmq_adapter.RabbitMQAdapter(config_manager_mock)
        config = adapter._get_config()

        expected_config = {
            'username': 'user',
            'password': 'pass',
            'host': 'localhost',
            'port': 5672,
            'vhost': '/',
            'infrastructure': {'queues': [{'name': 'Q.bridge.input'}, {'name': 'Q.bridge.result'}]}
        }
        assert config == expected_config
        config_manager_mock.get_rabbitmq_config.assert_called()


class TestQueueSubscription:
    """Tests for queue subscription logic."""

    def test_init_with_empty_queues_list(self, config_manager_mock):
        """Test initialization with empty queues list."""
        config_manager_mock.get_rabbitmq_config.return_value = {
            'username': 'user',
            'password': 'pass',
            'host': 'localhost',
            'port': 5672,
            'vhost': '/',
            'infrastructure': {'queues': []}
        }

        mock_channel = mock.MagicMock()
        mock_conn = mock.MagicMock()
        mock_conn.channel.return_value = mock_channel

        with mock.patch.object(rabbitmq_adapter.pika,
                               "PlainCredentials"), \
                mock.patch.object(rabbitmq_adapter.pika,
                                  "ConnectionParameters"), \
                mock.patch.object(rabbitmq_adapter.pika,
                                  "BlockingConnection", return_value=mock_conn):

            adapter = rabbitmq_adapter.RabbitMQAdapter(config_manager_mock) # pylint: disable=unused-variable
            mock_channel.basic_consume.assert_not_called()

    def test_init_with_queue_without_name(self, config_manager_mock):
        """Test initialization with queue configuration missing name."""
        config_manager_mock.get_rabbitmq_config.return_value = {
            'username': 'user',
            'password': 'pass',
            'host': 'localhost',
            'port': 5672,
            'vhost': '/',
            'infrastructure': {'queues': [{'type': 'input'}, {'name': 'Q.bridge.result'}]}
        }

        mock_channel = mock.MagicMock()
        mock_conn = mock.MagicMock()
        mock_conn.channel.return_value = mock_channel

        with mock.patch.object(rabbitmq_adapter.pika,
                               "PlainCredentials"), \
                mock.patch.object(rabbitmq_adapter.pika,
                                  "ConnectionParameters"), \
                mock.patch.object(rabbitmq_adapter.pika,
                                  "BlockingConnection", return_value=mock_conn):

            adapter = rabbitmq_adapter.RabbitMQAdapter(config_manager_mock) # pylint: disable=unused-variable
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

        # These methods should not be called when stopping from consumer thread
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
