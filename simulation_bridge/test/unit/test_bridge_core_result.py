"""Tests for BridgeCore result routing, bridge_index, and publishing."""

from unittest.mock import MagicMock, patch

from pika.exceptions import AMQPConnectionError

from simulation_bridge.src.core.routing_table import RoutingEntry
from .conftest import result_message

# pylint: disable=unused-argument,protected-access,redefined-outer-name


class TestHandleResultMessage:
    """Tests for handle_result_message routing-table flow."""

    def test_result_routed_via_rabbitmq(
            self, bridge_core_instance, patch_basic_publish):
        """RabbitMQ result published to ex.bridge.result."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='matlab', request_id='r1',
            bridge_index='idx1'))
        bridge_core_instance.handle_result_message(
            None, message=result_message(
                request_id='r1', bridge_index='idx1'))
        patch_basic_publish.assert_called_once()
        kw = patch_basic_publish.call_args[1]
        assert kw['exchange'] == 'ex.bridge.result'

    def test_result_routed_via_mqtt(self, bridge_core_instance):
        """MQTT result calls the MQTT adapter."""
        mqtt = MagicMock()
        bridge_core_instance.adapters['mqtt'] = mqtt
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='mqtt', pa_s='rabbitmq', dt='DT_2',
            sim_type='simul8', request_id='r2',
            bridge_index='idx2'))
        bridge_core_instance.handle_result_message(
            None, message=result_message(
                request_id='r2', bridge_index='idx2'))
        mqtt.publish_result_message_mqtt.assert_called_once()
        fwd = mqtt.publish_result_message_mqtt.call_args
        assert fwd[1]['message']['destinations'] == ['DT_2']

    def test_result_routed_via_rest(self, bridge_core_instance):
        """REST result calls the REST adapter."""
        rest = MagicMock()
        bridge_core_instance.adapters['rest'] = rest
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rest', pa_s='rabbitmq', dt='DT_3',
            sim_type='octave', request_id='r3',
            bridge_index='idx3'))
        bridge_core_instance.handle_result_message(
            None, message=result_message(
                request_id='r3', bridge_index='idx3'))
        rest.publish_result_message_rest.assert_called_once()
        fwd = rest.publish_result_message_rest.call_args
        assert fwd[1]['message']['destinations'] == ['DT_3']

    def test_result_routed_via_inmemory(self, bridge_core_instance):
        """Inmemory result calls _handle_result."""
        mem = MagicMock()
        bridge_core_instance.adapters['inmemory'] = mem
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='inmemory', pa_s='rabbitmq', dt='DT_4',
            sim_type='matlab', request_id='r4',
            bridge_index='idx4'))
        bridge_core_instance.handle_result_message(
            None, message=result_message(
                request_id='r4', bridge_index='idx4'))
        mem._handle_result.assert_called_once()
        fwd = mem._handle_result.call_args
        assert fwd[1]['message']['destinations'] == ['DT_4']

    def test_discarded_when_no_entry(
            self, bridge_core_instance,
            mock_logger, patch_basic_publish):
        """Result without routing entry is discarded."""
        bridge_core_instance.handle_result_message(
            None, message=result_message(request_id='nope'))
        patch_basic_publish.assert_not_called()
        mock_logger.warning.assert_called_once()

    def test_entry_removed_on_terminal(
            self, bridge_core_instance, patch_basic_publish):
        """Entry removed when result has terminal status."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='matlab', request_id='r5',
            bridge_index='idx5'))
        bridge_core_instance.handle_result_message(
            None, message=result_message(
                request_id='r5', status='completed',
                bridge_index='idx5'))
        assert bridge_core_instance.routing_table.lookup('r5') is None

    def test_entry_kept_on_non_terminal(
            self, bridge_core_instance, patch_basic_publish):
        """Entry kept when result has non-terminal status."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='matlab', request_id='r6',
            bridge_index='idx6'))
        bridge_core_instance.handle_result_message(
            None, message=result_message(
                request_id='r6', status='pending',
                bridge_index='idx6'))
        assert (
            bridge_core_instance.routing_table.lookup('r6')
            is not None)

    def test_streaming_entry_kept_on_terminal(
            self, bridge_core_instance, patch_basic_publish):
        """Streaming entry survives a terminal status."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='streaming', request_id='r7',
            bridge_index='idx7'))
        bridge_core_instance.handle_result_message(
            None, message=result_message(
                request_id='r7', status='completed',
                bridge_index='idx7'))
        assert (
            bridge_core_instance.routing_table.lookup('r7')
            is not None)

    def test_interactive_entry_kept_on_terminal(
            self, bridge_core_instance, patch_basic_publish):
        """Interactive entry survives a terminal status."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='interactive', request_id='r8',
            bridge_index='idx8'))
        bridge_core_instance.handle_result_message(
            None, message=result_message(
                request_id='r8', status='completed',
                bridge_index='idx8'))
        assert (
            bridge_core_instance.routing_table.lookup('r8')
            is not None)


class TestResultRabbitmqBackwardCompat:
    """handle_result_rabbitmq_message delegates correctly."""

    def test_publishes(
            self, bridge_core_instance, patch_basic_publish):
        """Backward-compat alias publishes to result exchange."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='unknown', request_id='unknown',
            bridge_index='bw'))
        message = {
            'request_id': 'unknown', 'source': 'src',
            'simulation': {}, 'data': 'result',
            'bridge_index': 'bw',
        }
        bridge_core_instance.handle_result_rabbitmq_message(
            None, message=message)
        patch_basic_publish.assert_called_once()
        kw = patch_basic_publish.call_args[1]
        assert kw['exchange'] == 'ex.bridge.result'


class TestResultUnknownMessage:
    """Tests for handle_result_unknown_message."""

    def test_routes_via_table_if_entry(
            self, bridge_core_instance, patch_basic_publish):
        """Unknown-protocol result routed via routing table."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='matlab', request_id='r7',
            bridge_index='idx7'))
        bridge_core_instance.handle_result_unknown_message(
            None, message=result_message(
                request_id='r7', bridge_index='idx7'))
        patch_basic_publish.assert_called_once()

    def test_logs_error_when_no_entry(
            self, bridge_core_instance, mock_logger):
        """Logs error when no routing entry exists."""
        bridge_core_instance.handle_result_unknown_message(
            None, message={
                'request_id': 'nope', 'error': 'bad'})
        mock_logger.error.assert_called_once()


class TestBridgeIndexValidation:
    """Tests for bridge_index anti-spoofing validation."""

    def test_mismatched_index_discards(
            self, bridge_core_instance,
            patch_basic_publish, mock_logger):
        """Result with wrong bridge_index is discarded."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='matlab', request_id='v1',
            bridge_index='correct'))
        bridge_core_instance.handle_result_message(
            None, message=result_message(
                request_id='v1', bridge_index='wrong'))
        patch_basic_publish.assert_not_called()
        mock_logger.warning.assert_called()

    def test_missing_index_allowed_backward_compat(
            self, bridge_core_instance,
            patch_basic_publish):
        """Result missing bridge_index is allowed for backward compat."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='matlab', request_id='v2',
            bridge_index='some_idx'))
        bridge_core_instance.handle_result_message(
            None, message=result_message(request_id='v2'))
        patch_basic_publish.assert_called_once()

    def test_matching_index_routes(
            self, bridge_core_instance, patch_basic_publish):
        """Correct bridge_index allows normal routing."""
        bridge_core_instance.routing_table.add(RoutingEntry(
            pa_n='rabbitmq', pa_s='rabbitmq', dt='DT_1',
            sim_type='matlab', request_id='v3',
            bridge_index='good'))
        bridge_core_instance.handle_result_message(
            None, message=result_message(
                request_id='v3', bridge_index='good'))
        patch_basic_publish.assert_called_once()


class TestPublishMessage:
    """Tests for _publish_message delegation to BridgePublisher."""

    def test_success(
            self, bridge_core_instance,
            patch_basic_publish, mock_logger):
        """Successfully publish a message."""
        message = {'simulation': {'request_id': '1'}}
        bridge_core_instance._publish_message(
            'prod', 'cons', message,
            exchange='ex.test', protocol='test')
        patch_basic_publish.assert_called_once()

    def test_retry_on_connection_loss(
            self, bridge_core_instance,
            patch_basic_publish, mock_logger):
        """Reconnect and retry on AMQP error."""
        def side_effect(*args, **kwargs):
            if not hasattr(side_effect, 'called'):
                side_effect.called = True
                raise AMQPConnectionError("lost")
            return True

        patch_basic_publish.side_effect = side_effect
        message = {'simulation': {'request_id': '1'}}
        with patch.object(
            bridge_core_instance._publisher,
            '_initialize_connection',
        ) as init_conn:
            bridge_core_instance._publish_message(
                'prod', 'cons', message,
                exchange='ex.test', protocol='test')
            assert patch_basic_publish.call_count == 2
            init_conn.assert_called_once()
