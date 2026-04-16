"""
Test suite for bridge_core.py using pytest and unittest.mock.

This module contains structured and focused tests for BridgeCore class
and related functions, verifying message handling, connection management,
routing-table integration, and error handling behaviors.
"""

from unittest.mock import MagicMock, patch
import pytest
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from simulation_bridge.src.core import bridge_core
from simulation_bridge.src.core.routing_table import RoutingEntry

# pylint: disable=too-many-arguments,unused-argument,protected-access,redefined-outer-name


@pytest.fixture
def config_manager_mock(dummy_credentials):
    """Fixture providing a ConfigManager mock with RabbitMQ config."""
    cm = MagicMock()
    cm.get_rabbitmq_config.return_value = {
        'host': 'localhost',
        'port': 5672,
        'username': dummy_credentials['user']['username'],
        'password': dummy_credentials['user']['password'],
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


def _valid_input_message(request_id='123', client_id='clientA',
                         simulator='simX', sim_type='typeA', timeout=60):
    """Helper to build a valid simulation request message."""
    return {
        'simulation': {
            'request_id': request_id,
            'client_id': client_id,
            'simulator': simulator,
            'type': sim_type,
            'file': 'file1',
            'timestamp': '2024-01-01T00:00:00Z',
            'timeout': timeout,
            'inputs': {},
            'outputs': {}
        }
    }


def _result_message(request_id='123', source='simX', status='completed',
                    sim_type='typeA', destinations=None):
    """Helper to build a simulation result message."""
    return {
        'request_id': request_id,
        'source': source,
        'status': status,
        'destinations': destinations or ['clientA'],
        'simulation': {'type': sim_type},
    }


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

    def test_routing_table_created(self, bridge_core_instance):
        """BridgeCore initializes with an empty routing table."""
        assert len(bridge_core_instance.routing_table) == 0


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
        message = _valid_input_message()
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

    def test_handle_input_message_registers_routing_entry(
            self, bridge_core_instance, patch_basic_publish):
        """A valid input message creates a routing-table entry."""
        message = _valid_input_message(request_id='abc', client_id='DT_1',
                                       sim_type='matlab', timeout=120)
        bridge_core_instance.handle_input_message(
            None, message=message, producer='DT_1', consumer='sim',
            protocol='rest')
        entry = bridge_core_instance.routing_table.lookup('abc')
        assert entry is not None
        assert entry.pa_n == 'rest'
        assert entry.pa_s == 'rabbitmq'
        assert entry.dt == 'DT_1'
        assert entry.sim_type == 'matlab'
        assert entry.timeout_seconds == 120

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


class TestHandleResultMessage:
    """Tests for the unified handle_result_message routing-table flow."""

    def test_result_routed_via_rabbitmq(self, bridge_core_instance,
                                        patch_basic_publish):
        """Result for a request that arrived via RabbitMQ is published to ex.bridge.result."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='matlab', request_id='r1'))
        bridge_core_instance.handle_result_message(
            None, message=_result_message(request_id='r1'))
        patch_basic_publish.assert_called_once()
        kwargs = patch_basic_publish.call_args[1]
        assert kwargs['exchange'] == 'ex.bridge.result'

    def test_result_routed_via_mqtt_adapter(self, bridge_core_instance):
        """Result for a request that arrived via MQTT calls the MQTT adapter."""
        mqtt_adapter = MagicMock()
        bridge_core_instance.adapters['mqtt'] = mqtt_adapter
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='mqtt', pa_s='rabbitmq', dt='DT_2',
            sim_type='simul8', request_id='r2'))
        msg = _result_message(request_id='r2')
        bridge_core_instance.handle_result_message(None, message=msg)
        mqtt_adapter.publish_result_message_mqtt.assert_called_once()

    def test_result_routed_via_rest_adapter(self, bridge_core_instance):
        """Result for a request that arrived via REST calls the REST adapter."""
        rest_adapter = MagicMock()
        bridge_core_instance.adapters['rest'] = rest_adapter
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rest', pa_s='rabbitmq', dt='DT_3',
            sim_type='octave', request_id='r3'))
        msg = _result_message(request_id='r3')
        bridge_core_instance.handle_result_message(None, message=msg)
        rest_adapter.publish_result_message_rest.assert_called_once()

    def test_result_routed_via_inmemory_adapter(self, bridge_core_instance):
        """Result for a request that arrived via inmemory calls _handle_result."""
        inmemory_adapter = MagicMock()
        bridge_core_instance.adapters['inmemory'] = inmemory_adapter
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='inmemory', pa_s='rabbitmq', dt='DT_4',
            sim_type='matlab', request_id='r4'))
        msg = _result_message(request_id='r4')
        bridge_core_instance.handle_result_message(None, message=msg)
        inmemory_adapter._handle_result.assert_called_once()

    def test_result_discarded_when_no_routing_entry(self, bridge_core_instance,
                                                     mock_logger, patch_basic_publish):
        """Result is discarded with a warning when no routing entry exists."""
        bridge_core_instance.handle_result_message(
            None, message=_result_message(request_id='unknown'))
        patch_basic_publish.assert_not_called()
        mock_logger.warning.assert_called_once()

    def test_entry_removed_on_terminal_status(self, bridge_core_instance,
                                               patch_basic_publish):
        """Routing entry is removed when the result has a terminal status."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='matlab', request_id='r5'))
        bridge_core_instance.handle_result_message(
            None, message=_result_message(request_id='r5', status='completed'))
        assert bridge_core_instance.routing_table.lookup('r5') is None

    def test_entry_kept_on_non_terminal_status(self, bridge_core_instance,
                                                patch_basic_publish):
        """Routing entry is kept when the result has a non-terminal status."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='matlab', request_id='r6'))
        bridge_core_instance.handle_result_message(
            None, message=_result_message(request_id='r6', status='pending'))
        assert bridge_core_instance.routing_table.lookup('r6') is not None


class TestHandleResultRabbitmqMessageBackwardCompat:
    """Backward-compat alias delegates to handle_result_message."""

    def test_handle_result_rabbitmq_message_publishes(self, bridge_core_instance,
                                                      patch_basic_publish):
        """Publishes RabbitMQ result message correctly via routing table."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='unknown', request_id='unknown'))
        message = {
            'request_id': 'unknown',
            'source': 'src',
            'simulation': {},
            'data': 'result'
        }
        bridge_core_instance.handle_result_rabbitmq_message(
            None, message=message)
        patch_basic_publish.assert_called_once()
        kwargs = patch_basic_publish.call_args[1]
        assert kwargs['exchange'] == 'ex.bridge.result'


class TestHandleResultUnknownMessage:
    """Tests for handle_result_unknown_message."""

    def test_routes_via_routing_table_if_entry_exists(
            self, bridge_core_instance, patch_basic_publish):
        """Unknown-protocol result is routed if routing table has an entry."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='matlab', request_id='r7'))
        bridge_core_instance.handle_result_unknown_message(
            None, message=_result_message(request_id='r7'))
        patch_basic_publish.assert_called_once()

    def test_logs_error_when_no_entry(self, bridge_core_instance, mock_logger):
        """Logs error when unknown-protocol result has no routing entry."""
        bridge_core_instance.handle_result_unknown_message(
            None, message={'request_id': 'nope', 'error': 'bad protocol'})
        mock_logger.error.assert_called_once()


class TestPublishMessage:
    "Tests for _publish_message method publishing messages to RabbitMQ"

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
