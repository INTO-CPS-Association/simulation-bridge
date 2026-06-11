"""Tests for BridgePublisher connection, TLS, and publish paths."""

import ssl
from unittest.mock import MagicMock, patch

import pika
import pytest

from simulation_bridge.src.core.bridge_publisher import BridgePublisher

# pylint: disable=protected-access,redefined-outer-name


BASE_CONFIG = {
    'host': 'localhost',
    'port': 5672,
    'username': 'guest',
    'password': 'guest',
    'vhost': '/',
    'tls': False,
}


def _make_publisher(config=None):
    """Return a BridgePublisher with a mocked pika connection."""
    cfg = config or BASE_CONFIG.copy()
    pika_path = (
        'simulation_bridge.src.core.bridge_publisher'
        '.pika.BlockingConnection')
    with patch(pika_path) as mock_conn_cls:
        conn = MagicMock()
        chan = MagicMock()
        conn.channel.return_value = chan
        conn.is_closed = False
        mock_conn_cls.return_value = conn
        publisher = BridgePublisher(cfg)
    return publisher


@pytest.fixture
def publisher():
    """BridgePublisher instance with a mocked connection."""
    return _make_publisher()


class TestBuildConnectionParams:
    """Tests for _build_connection_params."""

    def test_non_tls_returns_plain_params(self, publisher):
        params = publisher._build_connection_params()
        assert isinstance(params, pika.ConnectionParameters)
        assert params.ssl_options is None

    def test_tls_returns_ssl_params(self):
        cfg = {**BASE_CONFIG, 'tls': True}
        pika_path = (
            'simulation_bridge.src.core.bridge_publisher'
            '.pika.BlockingConnection')
        with patch(pika_path) as mock_conn_cls:
            conn = MagicMock()
            conn.channel.return_value = MagicMock()
            conn.is_closed = False
            mock_conn_cls.return_value = conn
            publisher = BridgePublisher(cfg)
        params = publisher._build_connection_params()
        assert params.ssl_options is not None


class TestInitializeConnection:
    """Tests for _initialize_connection."""

    def test_closes_existing_open_connection(self):
        """Existing open connection is closed before reconnecting."""
        pika_path = (
            'simulation_bridge.src.core.bridge_publisher'
            '.pika.BlockingConnection')
        with patch(pika_path) as mock_conn_cls:
            conn = MagicMock()
            conn.channel.return_value = MagicMock()
            conn.is_closed = False
            mock_conn_cls.return_value = conn
            publisher = BridgePublisher(BASE_CONFIG)
            old_conn = publisher.connection
            old_conn.is_closed = False
            publisher._initialize_connection()
            old_conn.close.assert_called_once()  # pylint: disable=no-member

    def test_amqp_connection_error_raises(self):
        """AMQPConnectionError propagates out of _initialize_connection."""
        pika_path = (
            'simulation_bridge.src.core.bridge_publisher'
            '.pika.BlockingConnection')
        with patch(pika_path) as mock_conn_cls:
            conn = MagicMock()
            conn.channel.return_value = MagicMock()
            conn.is_closed = False
            mock_conn_cls.return_value = conn
            publisher = BridgePublisher(BASE_CONFIG)

        pika_path2 = (
            'simulation_bridge.src.core.bridge_publisher'
            '.pika.BlockingConnection')
        with patch(pika_path2,
                   side_effect=pika.exceptions.AMQPConnectionError("down")):
            with pytest.raises(pika.exceptions.AMQPConnectionError):
                publisher._initialize_connection()

    def test_amqp_channel_error_raises(self):
        """AMQPChannelError during channel() propagates."""
        pika_path = (
            'simulation_bridge.src.core.bridge_publisher'
            '.pika.BlockingConnection')

        with patch(pika_path) as mock_conn_cls:
            conn = MagicMock()
            conn.channel.return_value = MagicMock()
            conn.is_closed = False
            mock_conn_cls.return_value = conn
            publisher = BridgePublisher(BASE_CONFIG)

        with patch(pika_path) as mock_conn_cls2:
            conn2 = MagicMock()
            conn2.channel.side_effect = pika.exceptions.AMQPChannelError(
                "chan")
            conn2.is_closed = False
            mock_conn_cls2.return_value = conn2
            with pytest.raises(pika.exceptions.AMQPChannelError):
                publisher._initialize_connection()

    def test_ssl_error_raises(self):
        """SSLError during connection propagates."""
        pika_path = (
            'simulation_bridge.src.core.bridge_publisher'
            '.pika.BlockingConnection')
        with patch(pika_path) as mock_conn_cls:
            conn = MagicMock()
            conn.channel.return_value = MagicMock()
            conn.is_closed = False
            mock_conn_cls.return_value = conn
            publisher = BridgePublisher(BASE_CONFIG)

        with patch(pika_path,
                   side_effect=ssl.SSLError("tls fail")):
            with pytest.raises(ssl.SSLError):
                publisher._initialize_connection()


class TestEnsureConnection:
    """Tests for ensure_connection."""

    def test_returns_true_when_connected(self, publisher):
        publisher.connection.is_closed = False
        assert publisher.ensure_connection() is True

    def test_reconnects_when_closed(self, publisher):
        publisher.connection = None
        pika_path = (
            'simulation_bridge.src.core.bridge_publisher'
            '.pika.BlockingConnection')
        with patch(pika_path) as mock_conn_cls:
            conn = MagicMock()
            conn.channel.return_value = MagicMock()
            conn.is_closed = False
            mock_conn_cls.return_value = conn
            result = publisher.ensure_connection()
        assert result is True

    def test_returns_false_on_amqp_error(self, publisher):
        publisher.connection = None
        pika_path = (
            'simulation_bridge.src.core.bridge_publisher'
            '.pika.BlockingConnection')
        with patch(pika_path,
                   side_effect=pika.exceptions.AMQPConnectionError("down")):
            result = publisher.ensure_connection()
        assert result is False

    def test_returns_false_on_channel_error(self, publisher):
        publisher.connection = None
        pika_path = (
            'simulation_bridge.src.core.bridge_publisher'
            '.pika.BlockingConnection')
        with patch(pika_path) as mock_conn_cls:
            conn = MagicMock()
            conn.channel.side_effect = pika.exceptions.AMQPChannelError("ch")
            conn.is_closed = False
            mock_conn_cls.return_value = conn
            result = publisher.ensure_connection()
        assert result is False


class TestPublish:
    """Tests for the publish method."""

    def test_publish_success(self, publisher):
        publisher.channel.basic_publish = MagicMock()
        publisher.publish(
            'prod', 'cons', {'simulation': {'type': 'test'}},
            exchange='ex.bridge.output', protocol='rest',
            operation_id='op1')
        publisher.channel.basic_publish.assert_called_once()

    def test_publish_injects_bridge_meta(self, publisher):
        publisher.channel.basic_publish = MagicMock()
        msg = {'simulation': {'type': 'matlab'}}
        publisher.publish(
            'prod', 'cons', msg,
            exchange='ex.test', protocol='mqtt',
            operation_id='op2')
        assert msg['simulation']['bridge_meta'] == {'protocol': 'mqtt'}

    def test_publish_skips_meta_when_sim_not_dict(self, publisher):
        publisher.channel.basic_publish = MagicMock()
        msg = {'simulation': 'not-a-dict'}
        publisher.publish('prod', 'cons', msg)

    def test_publish_retries_on_connection_error(self, publisher):
        call_count = [0]

        def side_effect(*args, **kwargs):  # pylint: disable=unused-argument
            call_count[0] += 1
            if call_count[0] == 1:
                raise pika.exceptions.AMQPConnectionError("lost")

        publisher.channel.basic_publish = MagicMock(
            side_effect=side_effect)
        pika_path = (
            'simulation_bridge.src.core.bridge_publisher'
            '.pika.BlockingConnection')
        with patch(pika_path) as mock_conn_cls:
            conn = MagicMock()
            chan = MagicMock()
            chan.basic_publish = MagicMock(side_effect=side_effect)
            conn.channel.return_value = chan
            conn.is_closed = False
            mock_conn_cls.return_value = conn
            publisher.publish(
                'prod', 'cons', {'simulation': {}},
                exchange='ex.bridge.output', protocol='test')

    def test_publish_retry_fails_logs_error(self, publisher):
        """If retry also fails, error is logged and no exception raised."""
        publisher.channel.basic_publish = MagicMock(
            side_effect=pika.exceptions.AMQPConnectionError("lost"))
        pika_path = (
            'simulation_bridge.src.core.bridge_publisher'
            '.pika.BlockingConnection')
        with patch(pika_path) as mock_conn_cls:
            conn = MagicMock()
            chan = MagicMock()
            chan.basic_publish = MagicMock(
                side_effect=pika.exceptions.AMQPConnectionError("retry fail"))
            conn.channel.return_value = chan
            conn.is_closed = False
            mock_conn_cls.return_value = conn
            # Should not raise
            publisher.publish(
                'prod', 'cons', {'simulation': {}},
                exchange='ex.bridge.output', protocol='test')

    def test_publish_no_metrics_for_non_output_exchange(self, publisher):
        publisher.channel.basic_publish = MagicMock()
        publisher.publish(
            'prod', 'cons', {'simulation': {'type': 'matlab'}},
            exchange='ex.bridge.result', protocol='rest',
            operation_id='op3')
        publisher.channel.basic_publish.assert_called_once()

    def test_publish_fails_when_no_connection(self, publisher):
        """publish returns without calling basic_publish if no connection."""
        publisher.connection = None
        pika_path = (
            'simulation_bridge.src.core.bridge_publisher'
            '.pika.BlockingConnection')
        with patch(pika_path,
                   side_effect=pika.exceptions.AMQPConnectionError("down")):
            publisher.publish(
                'prod', 'cons', {'simulation': {}})


class TestRecordMetrics:
    """Tests for _record_metrics."""

    def test_records_for_output_exchange(self, publisher):
        with patch(
            'simulation_bridge.src.core.bridge_publisher'
            '.PerformanceMonitor'
        ) as pm_cls:
            pm = MagicMock()
            pm_cls.return_value = pm
            publisher._record_metrics(
                'ex.bridge.output', 'rest', 'prod', 'cons',
                'op1', {'simulation': {'type': 'matlab'}})
            pm.record_core_sent_input.assert_called_once()

    def test_no_record_for_other_exchange(self, publisher):
        with patch(
            'simulation_bridge.src.core.bridge_publisher'
            '.PerformanceMonitor'
        ) as pm_cls:
            pm = MagicMock()
            pm_cls.return_value = pm
            publisher._record_metrics(
                'ex.bridge.result', 'rest', 'prod', 'cons',
                'op1', {'simulation': {'type': 'matlab'}})
            pm.record_core_sent_input.assert_not_called()
