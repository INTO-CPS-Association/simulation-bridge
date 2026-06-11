"""Tests for BridgeCore initialisation, connection, and input handling."""

from unittest.mock import MagicMock, patch
import json

from pika.exceptions import AMQPChannelError

from simulation_bridge.src.core import bridge_core
from .conftest import valid_input_message  # noqa: F401

# pylint: disable=unused-argument,protected-access,redefined-outer-name


class TestInitialization:
    """Tests for BridgeCore initialization and connection setup."""

    def test_initialize_rabbitmq_connection_success(
            self, config_manager_mock, adapters_mock, mock_logger):
        """Verify successful RabbitMQ connection initialization."""
        pika_path = (
            'simulation_bridge.src.core.bridge_publisher'
            '.pika.BlockingConnection')
        with patch(pika_path) as blocking_conn:
            conn_mock = MagicMock()
            chan_mock = MagicMock()
            conn_mock.channel.return_value = chan_mock
            blocking_conn.return_value = conn_mock
            bridge_core.BridgeCore(
                config_manager_mock, adapters_mock)
            blocking_conn.assert_called_once()
            conn_mock.channel.assert_called_once()

    def test_routing_table_created(self, bridge_core_instance):
        """BridgeCore initializes with an empty routing table."""
        assert len(bridge_core_instance.routing_table) == 0


class TestEnsureConnection:
    """Tests for _ensure_connection method."""

    def test_ensure_connection_active(self, bridge_core_instance):
        """Return True when connection is active."""
        bridge_core_instance.connection.is_closed = False
        result = bridge_core_instance._ensure_connection()
        assert result is True

    def test_ensure_connection_closed_reconnects(
            self, bridge_core_instance, mock_logger):
        """Reconnect when connection is closed and return True."""
        bridge_core_instance.connection.is_closed = True
        with patch.object(
            bridge_core_instance._publisher,
            '_initialize_connection',
        ) as init_conn:
            init_conn.return_value = None
            result = bridge_core_instance._ensure_connection()
            init_conn.assert_called_once()
            assert result is True

    def test_ensure_connection_fails_returns_false(
            self, bridge_core_instance, mock_logger):
        """Return False if reconnection fails."""
        bridge_core_instance._publisher.connection = None
        bridge_core_instance.connection = None
        with patch.object(
            bridge_core_instance._publisher,
            '_initialize_connection',
            side_effect=AMQPChannelError("err"),
        ):
            result = bridge_core_instance._ensure_connection()
            assert result is False


class TestHandleInputMessage:
    """Tests for handle_input_message processing."""

    def test_handle_input_message_valid(
            self, bridge_core_instance,
            patch_basic_publish, mock_logger):
        """Handle valid input message and publish to RabbitMQ."""
        message = valid_input_message()
        bridge_core_instance.handle_input_message(
            None, message=message, producer='prod',
            consumer='cons', protocol='mqtt')
        patch_basic_publish.assert_called_once()
        kw = patch_basic_publish.call_args[1]
        assert kw.get('exchange') == 'ex.bridge.output'
        assert kw.get('routing_key') == 'prod.cons'
        body = kw.get('body')
        assert isinstance(body, str)
        assert '"request_id": "123"' in body

    def test_registers_routing_entry(
            self, bridge_core_instance, patch_basic_publish):
        """A valid input creates a routing-table entry."""
        message = valid_input_message(
            request_id='abc', client_id='DT_1',
            sim_type='matlab', timeout=900)
        bridge_core_instance.handle_input_message(
            None, message=message, producer='DT_1',
            consumer='sim', protocol='rest')
        entry = bridge_core_instance.routing_table.lookup('abc')
        assert entry is not None
        assert entry.pa_n == 'rest'
        assert entry.pa_s == 'rabbitmq'
        assert entry.dt == 'DT_1'
        assert entry.sim_type == 'matlab'
        assert entry.timeout_seconds == 900
        assert len(entry.bridge_index) == 64

    def test_missing_simulation_still_publishes(
            self, bridge_core_instance,
            patch_basic_publish, mock_logger):
        """Message with minimal simulation fields still publishes."""
        message = {'simulation': {
            'request_id': 'unknown', 'client_id': '',
            'simulator': '', 'type': '', 'file': '',
            'inputs': {}, 'outputs': {},
        }}
        bridge_core_instance.handle_input_message(
            None, message=message, producer='prod',
            consumer='cons', protocol='rest')
        patch_basic_publish.assert_called_once()


class TestBridgeIndexInjection:
    """Tests that handle_input_message injects bridge_index."""

    def test_bridge_index_in_published_message(
            self, bridge_core_instance, patch_basic_publish):
        """Published message contains a bridge_index field."""
        message = valid_input_message(request_id='bi1')
        bridge_core_instance.handle_input_message(
            None, message=message, producer='p',
            consumer='c', protocol='rest')
        body = patch_basic_publish.call_args[1]['body']
        parsed = json.loads(body)
        bi = parsed['simulation']['bridge_index']
        assert len(bi) == 64

    def test_bridge_index_stored_in_entry(
            self, bridge_core_instance, patch_basic_publish):
        """Routing entry stores the same bridge_index."""
        message = valid_input_message(request_id='bi2')
        bridge_core_instance.handle_input_message(
            None, message=message, producer='p',
            consumer='c', protocol='mqtt')
        entry = bridge_core_instance.routing_table.lookup('bi2')
        assert entry is not None
        assert len(entry.bridge_index) == 64


class TestTimeoutClamping:
    """Tests that timeout is clamped to config bounds."""

    def test_clamped_to_max(
            self, bridge_core_instance, patch_basic_publish):
        """Timeout above max is clamped."""
        msg = valid_input_message(request_id='tc1', timeout=99999)
        bridge_core_instance.handle_input_message(
            None, message=msg, producer='p',
            consumer='c', protocol='rest')
        entry = bridge_core_instance.routing_table.lookup('tc1')
        assert entry.timeout_seconds == 1200

    def test_clamped_to_min(
            self, bridge_core_instance, patch_basic_publish):
        """Timeout below min is clamped."""
        msg = valid_input_message(request_id='tc2', timeout=1)
        bridge_core_instance.handle_input_message(
            None, message=msg, producer='p',
            consumer='c', protocol='rest')
        entry = bridge_core_instance.routing_table.lookup('tc2')
        assert entry.timeout_seconds == 30

    def test_in_range_kept(
            self, bridge_core_instance, patch_basic_publish):
        """Timeout within bounds is preserved."""
        msg = valid_input_message(request_id='tc3', timeout=900)
        bridge_core_instance.handle_input_message(
            None, message=msg, producer='p',
            consumer='c', protocol='rest')
        entry = bridge_core_instance.routing_table.lookup('tc3')
        assert entry.timeout_seconds == 900


class TestRequestDeduplication:
    """Tests that duplicate requests are discarded."""

    def test_duplicate_discarded(
            self, bridge_core_instance,
            patch_basic_publish, mock_logger):
        """Second identical request is discarded."""
        msg = valid_input_message(
            request_id='dup1', client_id='c1', simulator='s1')
        bridge_core_instance.handle_input_message(
            None, message=msg, producer='p',
            consumer='c', protocol='rest')
        assert patch_basic_publish.call_count == 1
        bridge_core_instance.handle_input_message(
            None, message=msg, producer='p',
            consumer='c', protocol='rest')
        assert patch_basic_publish.call_count == 1
        mock_logger.warning.assert_called()

    def test_different_request_id_not_duplicate(
            self, bridge_core_instance, patch_basic_publish):
        """Different request_id is not a duplicate."""
        msg1 = valid_input_message(
            request_id='d1', client_id='c1', simulator='s1')
        msg2 = valid_input_message(
            request_id='d2', client_id='c1', simulator='s1')
        bridge_core_instance.handle_input_message(
            None, message=msg1, producer='p',
            consumer='c', protocol='rest')
        bridge_core_instance.handle_input_message(
            None, message=msg2, producer='p',
            consumer='c', protocol='rest')
        assert patch_basic_publish.call_count == 2


class TestParseInputInvalid:
    """Tests for _parse_input with invalid messages."""

    def test_invalid_message_returns_none(
            self, bridge_core_instance,
            patch_basic_publish, mock_logger):
        """Invalid message is rejected without publishing."""
        bridge_core_instance.handle_input_message(
            None, message={'not_simulation': {}},
            producer='p', consumer='c', protocol='rest')
        patch_basic_publish.assert_not_called()
        mock_logger.error.assert_called()

    def test_empty_message_returns_none(
            self, bridge_core_instance,
            patch_basic_publish, mock_logger):
        """Empty message is rejected without publishing."""
        bridge_core_instance.handle_input_message(
            None, message={},
            producer='p', consumer='c', protocol='rest')
        patch_basic_publish.assert_not_called()


class TestPublishResultAdapter:
    """Tests for _publish_result_adapter error paths."""

    def test_no_adapter_logs_error(
            self, bridge_core_instance, mock_logger):
        """Logs error when adapter not found."""
        bridge_core_instance._publish_result_adapter(
            'unknown_pa', None, message={})
        mock_logger.error.assert_called()

    def test_no_method_name_logs_error(
            self, bridge_core_instance, mock_logger):
        """Logs error when no delivery method for protocol."""
        bridge_core_instance.adapters['custom_pa'] = MagicMock()
        bridge_core_instance._publish_result_adapter(
            'custom_pa', None, message={})
        mock_logger.error.assert_called()

    def test_adapter_missing_method_logs_error(
            self, bridge_core_instance, mock_logger):
        """Logs error when adapter exists but method is missing."""
        adapter = MagicMock(spec=[])  # no methods
        bridge_core_instance.adapters['mqtt'] = adapter
        bridge_core_instance._publish_result_adapter(
            'mqtt', None, message={})
        mock_logger.error.assert_called()


class TestInitializeRabbitmqConnection:
    """Tests for _initialize_rabbitmq_connection backward-compat wrapper."""

    def test_delegates_to_publisher(self, bridge_core_instance):
        """_initialize_rabbitmq_connection calls publisher's method."""
        with patch.object(
            bridge_core_instance._publisher,
            '_initialize_connection',
        ) as init_conn:
            bridge_core_instance._initialize_rabbitmq_connection()
            init_conn.assert_called_once()
