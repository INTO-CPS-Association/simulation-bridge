"""
Test module for simulation_bridge.src.core.bridge_infrastructure.

Uses pytest and unittest.mock to validate the behavior of RabbitMQInfrastructure.
"""

# pylint: disable=too-many-arguments, unused-argument, protected-access,
# pylint: disable=redefined-outer-name, attribute-defined-outside-init

from unittest import mock
import pytest

from simulation_bridge.src.core import bridge_infrastructure


@pytest.fixture
def config_fixture():
    """Returns a mock config manager with valid RabbitMQ config."""
    config = {
        'username': 'user',
        'password': 'pass',
        'host': 'localhost',
        'port': 5672,
        'virtual_host': '/',
        'infrastructure': {
            'exchanges': [
                {
                    'name': 'ex1',
                    'type': 'direct',
                    'durable': True,
                    'auto_delete': False,
                    'internal': False
                }
            ],
            'queues': [
                {
                    'name': 'q1',
                    'durable': True,
                    'exclusive': False,
                    'auto_delete': False
                }
            ],
            'bindings': [
                {
                    'exchange': 'ex1',
                    'queue': 'q1',
                    'routing_key': 'rk1'
                }
            ]
        }
    }
    manager = mock.Mock()
    manager.get_rabbitmq_config.return_value = config
    return manager


@pytest.fixture
def pika_fixture():
    """Provides a mocked connection and channel for RabbitMQ."""
    connection = mock.Mock()
    channel = mock.Mock()
    connection.channel.return_value = channel
    return connection, channel


class TestSetupMethod:
    """Tests for setup() method in RabbitMQInfrastructure."""

    @pytest.fixture(autouse=True)
    def _setup(self, config_fixture, monkeypatch, pika_fixture):
        """Patches Pika components and initializes the class under test."""
        conn, chan = pika_fixture
        monkeypatch.setattr('pika.PlainCredentials', lambda u, p: mock.Mock())
        monkeypatch.setattr('pika.BlockingConnection', lambda p: conn)
        monkeypatch.setattr('pika.ConnectionParameters', lambda **kwargs: mock.Mock())

        self.conn = conn
        self.chan = chan
        self.infra = bridge_infrastructure.RabbitMQInfrastructure(config_fixture)

    def test_setup_successful(self):
        """Test that all setup steps complete and close is called."""
        self.infra.setup()
        self.chan.exchange_declare.assert_called_once()
        self.chan.queue_declare.assert_called_once()
        self.chan.queue_bind.assert_called_once()
        self.conn.close.assert_called_once()

    def test_setup_raises_on_exchange_error(self):
        """Test setup raises exception and logs when exchange setup fails."""
        self.chan.exchange_declare.side_effect = Exception("Exchange error")
        with pytest.raises(Exception, match="Exchange error"):
            self.infra.setup()

    def test_setup_raises_on_queue_error(self):
        """Test setup raises exception when queue declaration fails."""
        self.chan.queue_declare.side_effect = Exception("Queue error")
        with pytest.raises(Exception, match="Queue error"):
            self.infra.setup()

    def test_setup_raises_on_binding_error(self):
        """Test setup raises exception when binding setup fails."""
        self.chan.queue_bind.side_effect = Exception("Binding error")
        with pytest.raises(Exception, match="Binding error"):
            self.infra.setup()


class TestReconnectMethod:
    """Tests for reconnect() method in RabbitMQInfrastructure."""

    @pytest.fixture(autouse=True)
    def _setup(self, config_fixture, monkeypatch, pika_fixture):
        """Prepare mocks and monkeypatches for reconnect tests."""
        conn, chan = pika_fixture
        monkeypatch.setattr('pika.PlainCredentials', lambda u, p: mock.Mock())
        monkeypatch.setattr('pika.BlockingConnection', lambda p: conn)
        monkeypatch.setattr('pika.ConnectionParameters', lambda **kwargs: mock.Mock())

        self.conn = conn
        self.chan = chan
        self.infra = bridge_infrastructure.RabbitMQInfrastructure(config_fixture)

    def test_reconnect_when_closed(self):
        """Should reconnect if the connection is closed."""
        self.conn.is_closed = True
        new_conn = mock.Mock()
        new_conn.channel.return_value = mock.Mock()

        with mock.patch('pika.BlockingConnection', return_value=new_conn):
            result = self.infra.reconnect()
            assert result == new_conn

    def test_reconnect_when_open(self):
        """Should not reconnect if the connection is already open."""
        self.conn.is_closed = False
        result = self.infra.reconnect()
        assert result == self.conn


class TestPrivateSetupMethods:
    """Tests for private _setup_exchanges, _setup_queues, _setup_bindings."""

    @pytest.fixture(autouse=True)
    def _setup(self, config_fixture, monkeypatch, pika_fixture):
        """Set up mocks and test instance."""
        conn, chan = pika_fixture
        monkeypatch.setattr('pika.PlainCredentials', lambda u, p: mock.Mock())
        monkeypatch.setattr('pika.BlockingConnection', lambda p: conn)
        monkeypatch.setattr('pika.ConnectionParameters', lambda **kwargs: mock.Mock())

        self.conn = conn
        self.chan = chan
        self.infra = bridge_infrastructure.RabbitMQInfrastructure(config_fixture)

    def test_exchanges_success(self):
        """Test _setup_exchanges declares configured exchanges."""
        self.infra._setup_exchanges()
        self.chan.exchange_declare.assert_called_once()

    def test_exchanges_exception(self):
        """Test _setup_exchanges raises and logs on error."""
        self.chan.exchange_declare.side_effect = Exception("exch error")
        with pytest.raises(Exception, match="exch error"):
            self.infra._setup_exchanges()

    def test_queues_success(self):
        """Test _setup_queues declares configured queues."""
        self.infra._setup_queues()
        self.chan.queue_declare.assert_called_once()

    def test_queues_exception(self):
        """Test _setup_queues raises and logs on error."""
        self.chan.queue_declare.side_effect = Exception("queue error")
        with pytest.raises(Exception, match="queue error"):
            self.infra._setup_queues()

    def test_bindings_success(self):
        """Test _setup_bindings binds queues correctly."""
        self.infra._setup_bindings()
        self.chan.queue_bind.assert_called_once()

    def test_bindings_exception(self):
        """Test _setup_bindings raises and logs on error."""
        self.chan.queue_bind.side_effect = Exception("bind error")
        with pytest.raises(Exception, match="bind error"):
            self.infra._setup_bindings()
