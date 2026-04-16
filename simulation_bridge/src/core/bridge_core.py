"""
Core bridge module for message routing between different protocols.

This module handles message routing between RabbitMQ, MQTT, and REST protocols,
providing a unified interface for cross-protocol communication.  A dynamic
routing table (see research paper, Table I) tracks in-flight simulation
requests so that responses can be correlated and routed back to the correct
Digital Twin via the correct north-bound Protocol Adapter.
"""

from typing import Dict, Any, Optional
import json
from datetime import datetime
import ssl
import pika
from pydantic import BaseModel
from ..utils.config_manager import ConfigManager
from ..utils.logger import get_logger
from ..utils.performance_monitor import PerformanceMonitor
from .routing_table import (
    RoutingTable, RoutingEntry, DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_MAX_TIMEOUT, DEFAULT_MIN_TIMEOUT,
    generate_bridge_index,
)

# Constants for RabbitMQ connection parameters
RABBITMQ_HEARTBEAT = 600  # 10 minutes heartbeat
RABBITMQ_BLOCKED_CONNECTION_TIMEOUT = 300  # 5 minutes timeout
RABBITMQ_CONNECTION_ATTEMPTS = 3  # Number of connection attempts
RABBITMQ_RETRY_DELAY = 5  # Delay between retries in seconds

# Maps north-bound PA name → adapter method that delivers results
_RESULT_METHOD_FOR_PA = {
    'mqtt': 'publish_result_message_mqtt',
    'rest': 'publish_result_message_rest',
    'inmemory': '_handle_result',
}

# Statuses that indicate a simulation run has reached a terminal state
_TERMINAL_STATUSES = frozenset({
    'completed', 'failed', 'error', 'aborted', 'cancelled',
})


logger = get_logger()


def datetime_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()  # It converts datetime to ISO 8601 string format
    raise TypeError(f"Type {obj.__class__.__name__} not serializable")

# Pydantic models for message validation


class SimulationModel(BaseModel):
    "Represents the details of a simulation request."
    request_id: str
    client_id: str
    simulator: str
    type: str
    timestamp: Optional[datetime] = None
    timeout: Optional[int] = None
    file: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    bridge_index: Optional[str] = None

class MessageModel(BaseModel):
    "Represents a message structure for simulation requests."
    simulation: SimulationModel

class BridgeCore:
    """
    Core bridge class for handling message routing between different protocols.

    Manages connections to RabbitMQ, MQTT, and REST endpoints, and routes
    messages between them based on a dynamic routing table that maps
    in-flight requests to their originating DT and north-bound PA.
    """

    def __init__(self, config_manager: ConfigManager, adapters: dict):
        """
        Initialize the bridge core with configuration and adapters.

        Args:
            config_manager: Configuration manager instance
            adapters: Dictionary of protocol adapters
        """
        self.config = config_manager.get_rabbitmq_config()
        full_cfg = config_manager.get_config()
        routing_cfg = full_cfg.get(
            'simulation_bridge', {}).get('routing', {})
        self._max_timeout = routing_cfg.get(
            'max_timeout_seconds', DEFAULT_MAX_TIMEOUT)
        self._min_timeout = routing_cfg.get(
            'min_timeout_seconds', DEFAULT_MIN_TIMEOUT)
        self.connection = None
        self.channel = None
        self._initialize_rabbitmq_connection()
        self.adapters = adapters
        self.routing_table = RoutingTable()
        logger.debug("Signals connected and bridge core initialized")

    def _initialize_rabbitmq_connection(self):
        """Initialize or reinitialize the RabbitMQ connection."""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()

            try:
                credentials = pika.PlainCredentials(
                    self.config['username'],
                    self.config['password']
                )

                if self.config.get('tls', False):
                    context = ssl.create_default_context()
                    context.minimum_version = ssl.TLSVersion.TLSv1_2
                    ssl_options = pika.SSLOptions(context, self.config['host'])
                    connection_params = pika.ConnectionParameters(
                        host=self.config['host'],
                        port=self.config['port'],
                        virtual_host=self.config['vhost'],
                        credentials=credentials,
                        ssl_options=ssl_options
                    )
                else:
                    connection_params = pika.ConnectionParameters(
                        host=self.config['host'],
                        port=self.config['port'],
                        virtual_host=self.config['vhost'],
                        credentials=credentials
                    )

                self.connection = pika.BlockingConnection(connection_params)

            except (pika.exceptions.AMQPConnectionError, ssl.SSLError) as e:
                logger.error(
                    "Failed to connect to RabbitMQ at %s:%s with TLS=%s",
                    self.config['host'], self.config['port'], self.config.get(
                        'tls', False)
                )
                logger.error("Error: %s", e)
                raise RuntimeError(
                    "Connection failed. Check TLS settings and port.") from e

            except Exception as e:
                logger.error(
                    "Unexpected error while connecting to RabbitMQ: %s", e)
                raise
            self.channel = self.connection.channel()
            logger.debug("RabbitMQ connection established successfully")
        except pika.exceptions.AMQPConnectionError as e:
            logger.error("Failed to initialize RabbitMQ connection: %s", e)
            raise
        except pika.exceptions.AMQPChannelError as e:
            logger.error("Failed to initialize RabbitMQ channel: %s", e)
            raise

    def _ensure_connection(self):
        """Ensure the RabbitMQ connection is active, reconnect if necessary."""
        try:
            if not self.connection or self.connection.is_closed:
                logger.warning(
                    "RabbitMQ connection is closed, attempting to reconnect...")
                self._initialize_rabbitmq_connection()
            return True
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError) as e:
            logger.error("Failed to ensure RabbitMQ connection: %s", e)
            return False

    def handle_input_message(self, sender, **kwargs):  # pylint: disable=unused-argument
        """
        Handle incoming messages and register a routing table entry.

        Args:
            **kwargs: Keyword arguments containing message data
        """
        # Initialize performance monitor
        performance_monitor = PerformanceMonitor()
        message_dict = kwargs.get('message', {})
        producer = kwargs.get('producer', 'unknown')
        simulation_type = message_dict.get(
            'simulation', {}).get('type', 'unknown')
        protocol = kwargs.get('protocol', 'unknown')
        operation_id = message_dict.get(
            'simulation', {}).get(
            'request_id', 'unknown')
        performance_monitor.record_core_received_input(
            operation_id, protocol, producer, simulation_type)
        try:
            message = MessageModel.model_validate(message_dict)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Invalid message format: %s", e)
            return
        simulation = message.simulation
        if simulation is None:
            request_id = 'unknown'
        else:
            request_id = simulation.request_id if simulation.request_id else 'unknown'
        producer = kwargs.get('producer', 'unknown')
        consumer = kwargs.get('consumer', 'unknown')

        # Register in routing table (PA_N=protocol, PA_S=rabbitmq)
        timeout = (
            simulation.timeout
            if simulation.timeout is not None
            else DEFAULT_TIMEOUT_SECONDS
        )
        timeout = max(self._min_timeout, min(timeout, self._max_timeout))

        # Deduplicate: discard if (request_id, client_id, simulator) seen
        if self.routing_table.has_request(
            request_id, simulation.client_id, simulation.simulator,
        ):
            logger.warning(
                "Duplicate request discarded: request_id=%s, "
                "client_id=%s, simulator=%s",
                request_id, simulation.client_id, simulation.simulator,
            )
            return

        # Generate anti-spoofing bridge_index
        bridge_idx = generate_bridge_index(
            protocol, 'rabbitmq', request_id)

        self.routing_table.add(
            RoutingEntry(
                pa_n=protocol,
                pa_s='rabbitmq',
                dt=simulation.client_id,
                sim_type=simulation.type,
                request_id=request_id,
                timeout_seconds=timeout,
                bridge_index=bridge_idx,
            ),
            client_id=simulation.client_id,
            simulator=simulation.simulator,
        )

        # Inject bridge_index into the outgoing message
        out_message = message.model_dump()
        out_message['simulation']['bridge_index'] = bridge_idx

        logger.info(
            "[%s] Handling incoming simulation request with ID: %s", protocol.upper(), request_id)
        self._publish_message(
            producer,
            consumer,
            out_message,
            protocol=protocol, operation_id=operation_id)

    def handle_result_message(self, sender, **kwargs):  # pylint: disable=unused-argument
        """
        Unified result handler that routes responses via the routing table.

        When a simulation result arrives the handler:
        1. Purges expired routing-table entries (opportunistic cleanup).
        2. Looks up the request_id in the routing table.
        3. Routes the result to the north-bound PA recorded in the entry.
        4. Removes the entry when the simulation reaches a terminal status.

        Args:
            **kwargs: Keyword arguments containing 'message' dict.
        """
        message = kwargs.get('message', {})
        request_id = message.get('request_id', 'unknown')

        # Opportunistic purge of stale entries
        self.routing_table.purge_expired()

        # Routing-table lookup
        entry = self.routing_table.lookup(request_id)
        if entry is None:
            logger.warning(
                "No routing entry for request_id=%s — discarding result",
                request_id,
            )
            return

        # Validate bridge_index (anti-spoofing)
        result_bridge_idx = message.get('bridge_index')
        if entry.bridge_index and result_bridge_idx != entry.bridge_index:
            logger.warning(
                "bridge_index mismatch for request_id=%s — discarding "
                "result (expected=%s, got=%s)",
                request_id, entry.bridge_index, result_bridge_idx,
            )
            return

        pa_n = entry.pa_n
        destination = entry.dt

        # Deliver via the correct north-bound PA using the routing-table
        # destination instead of trusting the inbound message payload.
        routed_kwargs = dict(kwargs)
        routed_message = dict(message)
        routed_message['destinations'] = [destination]
        routed_kwargs['message'] = routed_message
        self._route_result_to_adapter(pa_n, sender, **routed_kwargs)

        # Finalise if the simulation has reached a terminal state
        status = message.get('status', '')
        simulation_type = message.get(
            'simulation', {}).get('type', 'unknown')
        if status in _TERMINAL_STATUSES:
            self.routing_table.remove(request_id)
            # Record finalization only for the RabbitMQ direct-publish
            # path; MQTT/REST adapters handle their own perf recording.
            if pa_n == 'rabbitmq':
                performance_monitor = PerformanceMonitor()
                performance_monitor.record_result_sent(
                    request_id, pa_n, destination, simulation_type)
                performance_monitor.finalize_operation(
                    request_id, pa_n, destination, simulation_type)

    # keep old handler as alias for backward compatibility
    def handle_result_rabbitmq_message(self, sender, **kwargs):
        """Route a RabbitMQ-originating result through the routing table."""
        self.handle_result_message(sender, **kwargs)

    def handle_result_unknown_message(self, sender, **kwargs):  # pylint: disable=unused-argument
        """Handle results whose originating protocol could not be determined."""
        message = kwargs.get('message', {})
        request_id = message.get('request_id', 'unknown')

        # Try the routing table — it may still know how to route this
        entry = self.routing_table.lookup(request_id)
        if entry is not None:
            self.handle_result_message(sender, **kwargs)
            return

        logger.error(
            "Received result with unknown protocol and no routing entry: %s",
            message.get('error', request_id),
        )

    def _route_result_to_adapter(self, pa_n, sender, **kwargs):
        """Deliver a result message via the north-bound PA identified by *pa_n*.

        For RabbitMQ the result is published to the ``ex.bridge.result``
        exchange.  For every other PA the corresponding adapter method is
        invoked directly.
        """
        message = kwargs.get('message', {})

        if pa_n == 'rabbitmq':
            producer = message.get('source', 'unknown')
            consumer = 'result'
            operation_id = message.get('request_id', 'unknown')
            self._publish_message(
                producer,
                consumer,
                message,
                exchange='ex.bridge.result',
                protocol='rabbitmq',
                operation_id=operation_id,
            )
            return

        adapter = self.adapters.get(pa_n)
        if adapter is None:
            logger.error("No adapter registered for protocol '%s'", pa_n)
            return

        method_name = _RESULT_METHOD_FOR_PA.get(pa_n)
        if method_name is None:
            logger.error("No result delivery method mapped for protocol '%s'", pa_n)
            return

        method = getattr(adapter, method_name, None)
        if method is None:
            logger.error(
                "Adapter '%s' has no method '%s'", pa_n, method_name)
            return

        method(sender, **kwargs)

    def _publish_message(self, producer, consumer, message,  # pylint: disable=too-many-arguments, too-many-positional-arguments
                         exchange='ex.bridge.output', protocol='unknown', operation_id='unknown'):
        """
        Publish message to RabbitMQ exchange.

        Args:
            producer: Message producer identifier
            consumer: Message consumer identifier
            message: Message payload
            exchange: RabbitMQ exchange name
            protocol: Protocol identifier
        """
        if not self._ensure_connection():
            logger.error(
                "Cannot publish message: RabbitMQ connection is not available")
            return

        # Initialize performance monitor
        performance_monitor = PerformanceMonitor()
        simulation_type = message.get('simulation', {}).get('type', 'unknown')
        routing_key = f"{producer}.{consumer}"
        message['simulation']['bridge_meta'] = {
            'protocol': protocol
        }
        try:
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(message, default=datetime_serializer),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                )
            )
            logger.debug(
                "Message routed to exchange '%s': %s -> %s, protocol=%s",
                exchange, producer, consumer, protocol)
            # Record sent input time in performance monitor
            if exchange == 'ex.bridge.output':
                performance_monitor.record_core_sent_input(
                    operation_id, protocol, producer, simulation_type)
        except (pika.exceptions.AMQPConnectionError,
                pika.exceptions.AMQPChannelError) as e:
            logger.error("RabbitMQ connection error: %s", e)
            self._initialize_rabbitmq_connection()
            # Retry the publish operation once
            try:
                self.channel.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                    )
                )
                logger.debug(
                    "Message routed to exchange '%s' after reconnection: %s -> %s",
                    exchange, producer, consumer)
            except (pika.exceptions.AMQPConnectionError,
                    pika.exceptions.AMQPChannelError) as retry_e:
                logger.error(
                    "Failed to publish message after reconnection: %s", retry_e)
