"""
Test suite for bridge_core.py using pytest and unittest.mock.

This module contains structured and focused tests for BridgeCore class
and related functions, verifying message handling, connection management,
and error handling behaviors.
"""

from unittest.mock import MagicMock, patch
import pytest
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from simulation_bridge.src.core import bridge_core

# pylint: disable=too-many-arguments,unused-argument,protected-access,redefined-outer-name


@pytest.fixture
def config_manager_mock():
    """Fixture providing a ConfigManager mock with RabbitMQ config."""
    cm = MagicMock()
    cm.get_rabbitmq_config.return_value = {
        'host': 'localhost',
        'port': 5672,
        'username': 'user',
        'password': 'pass',
        'vhost': '/',
        'tls': False,
    }
    return cm


@pytest.fixture
def adapters_mock():
    """Fixture providing dummy adapters dict."""
    return {'dummy_protocol': MagicMock()}


@pytest.fixture
def bridge_core_instance(config_manager_mock, adapters_mock):
    """Fixture to create a BridgeCore instance with mocks."""
    with patch('simulation_bridge.src.core.bridge_core.pika.BlockingConnection') as blocking_conn:
        connection_mock = MagicMock()
        channel_mock = MagicMock()
        connection_mock.channel.return_value = channel_mock
        connection_mock.is_closed = False
        blocking_conn.return_value = connection_mock
        core = bridge_core.BridgeCore(config_manager_mock, adapters_mock)
        yield core


@pytest.fixture
def mock_logger():
    """Fixture to patch the logger in bridge_core."""
    with patch('simulation_bridge.src.core.bridge_core.logger') as log_mock:
        yield log_mock


@pytest.fixture
def patch_basic_publish(bridge_core_instance):
    """Fixture to patch channel.basic_publish."""
    with patch.object(bridge_core_instance.channel, 'basic_publish') as bp:
        yield bp


class TestInitialization:
    """Tests for BridgeCore initialization and connection setup."""

    def test_initialize_rabbitmq_connection_success(self, config_manager_mock,
                                                    adapters_mock, mock_logger):
        """Verify successful RabbitMQ connection initialization."""
        with patch('simulation_bridge.src.core.bridge_core.pika.BlockingConnection') as blocking_conn:  # pylint: disable=line-too-long
            conn_mock = MagicMock()
            chan_mock = MagicMock()
            conn_mock.channel.return_value = chan_mock
            blocking_conn.return_value = conn_mock

            core = bridge_core.BridgeCore(  # pylint: disable=unused-variable
                config_manager_mock,
                adapters_mock)

            blocking_conn.assert_called_once()
            conn_mock.channel.assert_called_once()
            mock_logger.debug.assert_any_call(
                "RabbitMQ connection established successfully")


class TestEnsureConnection:
    """Tests for _ensure_connection method ensuring connection health."""

    def test_ensure_connection_active(self, bridge_core_instance):
        """Return True when connection is active."""
        bridge_core_instance.connection.is_closed = False
        result = bridge_core_instance._ensure_connection()
        assert result is True

    def test_ensure_connection_closed_reconnects(self, bridge_core_instance,
                                                 mock_logger):
        """Reconnect when connection is closed and return True."""
        bridge_core_instance.connection.is_closed = True
        with patch.object(bridge_core_instance, '_initialize_rabbitmq_connection') as init_conn:
            init_conn.return_value = None
            result = bridge_core_instance._ensure_connection()
            init_conn.assert_called_once()
            assert result is True

    def test_ensure_connection_fails_returns_false(self, bridge_core_instance,
                                                   mock_logger):
        """Return False if reconnection fails with AMQP errors."""
        bridge_core_instance.connection = None
        with patch.object(bridge_core_instance, '_initialize_rabbitmq_connection',
                          side_effect=AMQPChannelError("chan error")), \
                patch('simulation_bridge.src.core.bridge_core.logger') as log_mock:
            result = bridge_core_instance._ensure_connection()
            assert result is False
            log_mock.error.assert_called_once()


class TestHandleInputMessage:
    "Tests for handle_input_message method processing input messages."

    def test_handle_input_message_valid(self, bridge_core_instance,
                                        patch_basic_publish, mock_logger):
        """Handle valid input message and publish to RabbitMQ."""
        message = {
            'simulation': {
                'request_id': '123',
                'client_id': 'clientA',
                'simulator': 'simX',
                'type': 'typeA',
                'file': 'file1',
                'timestamp': '2024-01-01T00:00:00Z',
                'timeout': 60,
                'inputs': {},
                'outputs': {}
            }
        }
        kwargs = {
            'message': message,
            'producer': 'prod',
            'consumer': 'cons',
            'protocol': 'mqtt'
        }
        bridge_core_instance.handle_input_message(None, **kwargs)
        patch_basic_publish.assert_called_once()
        call_args = patch_basic_publish.call_args
        args = call_args[0]  # pylint: disable=unused-variable
        kwargs = call_args[1]
        assert kwargs.get('exchange') == 'ex.bridge.output'
        assert kwargs.get('routing_key') == 'prod.cons'
        body = kwargs.get('body')
        assert isinstance(body, str)
        assert '"request_id": "123"' in body
        assert 'properties' in kwargs
        mock_logger.info.assert_called_once()

    def test_handle_input_message_missing_simulation(self, bridge_core_instance,
                                                     patch_basic_publish, mock_logger):
        """Handle message with missing simulation key gracefully."""
        message = {'simulation': {
            'request_id': 'unknown',
            'client_id': '',
            'simulator': '',
            'type': '',
            'file': '',
            'inputs': {},
            'outputs': {}
        }}
        kwargs = {
            'message': message,
            'producer': 'prod',
            'consumer': 'cons',
            'protocol': 'rest'
        }
        bridge_core_instance.handle_input_message(None, **kwargs)
        patch_basic_publish.assert_called_once()
        mock_logger.info.assert_called_once()


class TestHandleResultMessages:  # pylint: disable=too-few-public-methods
    "Tests for handling result messages from RabbitMQ and other protocols."""

    def test_handle_result_rabbitmq_message_publishes(self, bridge_core_instance,
                                                      patch_basic_publish):
        """Publishes RabbitMQ result message correctly."""
        message = {
            'source': 'src',
            'simulation': {},
            'data': 'result'
        }
        bridge_core_instance.handle_result_rabbitmq_message(
            None, message=message)
        patch_basic_publish.assert_called_once()
        kwargs = patch_basic_publish.call_args[1]
        assert kwargs['exchange'] == 'ex.bridge.result'


class TestPublishMessage:
    "Tests for _publish_message method publishing messages to RabbitMQ."""

    def test_publish_message_success(self, bridge_core_instance, patch_basic_publish,
                                     mock_logger):
        """Successfully publish a message on RabbitMQ."""
        message = {'simulation': {'request_id': '1'}}
        bridge_core_instance._publish_message(
            'prod', 'cons', message, exchange='ex.test', protocol='test')
        patch_basic_publish.assert_called_once()

        calls = mock_logger.debug.call_args_list
        assert any(
            call.args[0] == "Message routed to exchange '%s': %s -> %s, protocol=%s" and
            call.args[1] == 'ex.test' and
            call.args[2] == 'prod' and
            call.args[3] == 'cons' and
            call.args[4] == 'test'
            for call in calls
        )

    def test_publish_message_connection_lost_then_retries(self, bridge_core_instance,
                                                          patch_basic_publish,
                                                          mock_logger):
        """Reconnect and retry publish once if first attempt raises AMQP error."""
        def side_effect(*args, **kwargs):
            if not hasattr(side_effect, 'called'):
                side_effect.called = True
                raise AMQPConnectionError("conn lost")
            return True

        patch_basic_publish.side_effect = side_effect
        message = {'simulation': {'request_id': '1'}}
        with patch.object(bridge_core_instance, '_initialize_rabbitmq_connection') as init_conn:
            bridge_core_instance._publish_message(
                'prod', 'cons', message, exchange='ex.test', protocol='test')
            assert patch_basic_publish.call_count == 2
            init_conn.assert_called_once()
            calls = mock_logger.debug.call_args_list
            assert any(
                call.args[0] % call.args[1:] == "Message routed to exchange 'ex.test' after reconnection: prod -> cons"  # pylint: disable=line-too-long
                for call in calls
            )
