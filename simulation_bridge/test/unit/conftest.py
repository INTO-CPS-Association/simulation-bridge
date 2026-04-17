"""Shared fixtures and helpers for bridge_core unit tests."""

from unittest.mock import MagicMock, patch
import pytest

from simulation_bridge.src.core import bridge_core

# pylint: disable=redefined-outer-name


@pytest.fixture
def config_manager_mock(dummy_credentials):
    """ConfigManager mock with RabbitMQ and routing config."""
    cm = MagicMock()
    cm.get_rabbitmq_config.return_value = {
        'host': 'localhost',
        'port': 5672,
        'username': dummy_credentials['user']['username'],
        'password': dummy_credentials['user']['password'],
        'vhost': '/',
        'tls': False,
    }
    cm.get_config.return_value = {
        'simulation_bridge': {
            'bridge_id': 'test_bridge',
            'routing': {
                'max_timeout_seconds': 1200,
                'min_timeout_seconds': 30,
            },
        },
    }
    return cm


@pytest.fixture
def adapters_mock():
    """Dummy adapters dict."""
    return {'dummy_protocol': MagicMock()}


@pytest.fixture
def bridge_core_instance(config_manager_mock, adapters_mock):
    """BridgeCore instance with mocked RabbitMQ connection."""
    pika_path = (
        'simulation_bridge.src.core.bridge_publisher'
        '.pika.BlockingConnection')
    with patch(pika_path) as blocking_conn:
        connection_mock = MagicMock()
        channel_mock = MagicMock()
        connection_mock.channel.return_value = channel_mock
        connection_mock.is_closed = False
        blocking_conn.return_value = connection_mock
        core = bridge_core.BridgeCore(
            config_manager_mock, adapters_mock)
        yield core


@pytest.fixture
def mock_logger():
    """Patch the logger in bridge_core module."""
    with patch(
        'simulation_bridge.src.core.bridge_core.logger'
    ) as log_mock:
        yield log_mock


@pytest.fixture
def patch_basic_publish(bridge_core_instance):
    """Patch channel.basic_publish on the bridge_core_instance."""
    with patch.object(
        bridge_core_instance.channel, 'basic_publish'
    ) as bp:
        yield bp


def valid_input_message(
        request_id='123', client_id='clientA',
        simulator='simX', sim_type='typeA', timeout=60):
    """Build a valid simulation request message dict."""
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
            'outputs': {},
        }
    }


def result_message(
        request_id='123', source='simX', status='completed',
        sim_type='typeA', destinations=None, bridge_index=None):
    """Build a simulation result message dict."""
    msg = {
        'request_id': request_id,
        'source': source,
        'status': status,
        'destinations': destinations or ['clientA'],
        'simulation': {'type': sim_type},
    }
    if bridge_index is not None:
        msg['bridge_index'] = bridge_index
    return msg
