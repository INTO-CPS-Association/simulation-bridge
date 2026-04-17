"""Core bridge module for routing messages between protocol adapters."""

from ..utils.config_manager import ConfigManager
from ..utils.logger import get_logger
from ..utils.performance_monitor import PerformanceMonitor
from .bridge_publisher import BridgePublisher
from .models import MessageModel
from .routing_table import (
    RoutingTable, RoutingEntry, DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_MAX_TIMEOUT, DEFAULT_MIN_TIMEOUT,
    generate_bridge_index,
)

_RESULT_METHOD_FOR_PA = {
    'mqtt': 'publish_result_message_mqtt',
    'rest': 'publish_result_message_rest',
    'inmemory': '_handle_result',
}
_TERMINAL_STATUSES = frozenset({
    'completed', 'failed', 'error', 'aborted', 'cancelled',
})

logger = get_logger()


class BridgeCore:
    """Routes messages between protocol adapters via a routing table."""

    def __init__(self, config_manager: ConfigManager, adapters: dict):
        self.config = config_manager.get_rabbitmq_config()
        self._publisher = BridgePublisher(self.config)
        self.connection = self._publisher.connection
        self.channel = self._publisher.channel
        self._load_routing_config(config_manager)
        self.adapters = adapters
        self.routing_table = RoutingTable()
        logger.debug("Signals connected and bridge core initialized")

    def _load_routing_config(self, config_manager):
        """Extract timeout bounds from config."""
        full_cfg = config_manager.get_config()
        routing_cfg = full_cfg.get(
            'simulation_bridge', {}).get('routing', {})
        self._max_timeout = routing_cfg.get(
            'max_timeout_seconds', DEFAULT_MAX_TIMEOUT)
        self._min_timeout = routing_cfg.get(
            'min_timeout_seconds', DEFAULT_MIN_TIMEOUT)

    def handle_input_message(self, sender, **kwargs):  # pylint: disable=unused-argument
        """Validate, deduplicate, register and forward a request."""
        message_dict, protocol, producer, operation_id = (
            self._extract_input_meta(kwargs))
        sim_type = message_dict.get(
            'simulation', {}).get('type', 'unknown')
        PerformanceMonitor().record_core_received_input(
            operation_id, protocol, producer, sim_type)
        simulation = self._parse_input(message_dict)
        if simulation is None:
            return
        request_id = simulation.request_id or 'unknown'
        if self._is_duplicate(request_id, simulation):
            return
        bridge_idx, timeout = self._register_request(
            simulation, request_id, protocol)
        out_message = self._build_outgoing(simulation, bridge_idx)
        consumer = kwargs.get('consumer', 'unknown')
        logger.info(
            "[%s] Handling incoming simulation request "
            "with ID: %s", protocol.upper(), request_id)
        self._publish_message(
            producer, consumer, out_message,
            protocol=protocol, operation_id=operation_id)

    def _extract_input_meta(self, kwargs):
        """Return (message_dict, protocol, producer, operation_id)."""
        msg = kwargs.get('message', {})
        protocol = kwargs.get('protocol', 'unknown')
        producer = kwargs.get('producer', 'unknown')
        op_id = msg.get(
            'simulation', {}).get('request_id', 'unknown')
        return msg, protocol, producer, op_id

    def _parse_input(self, message_dict):
        """Validate and return SimulationModel or None."""
        try:
            message = MessageModel.model_validate(message_dict)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Invalid message format: %s", exc)
            return None
        return message.simulation

    def _is_duplicate(self, request_id, simulation):
        """Return True and log warning if request was seen before."""
        if self.routing_table.has_request(
            request_id, simulation.client_id,
            simulation.simulator,
        ):
            logger.warning(
                "Duplicate request discarded: request_id=%s, "
                "client_id=%s, simulator=%s",
                request_id, simulation.client_id,
                simulation.simulator)
            return True
        return False

    def _register_request(self, simulation, request_id, protocol):
        """Add routing entry; return (bridge_index, timeout)."""
        timeout = simulation.timeout or DEFAULT_TIMEOUT_SECONDS
        timeout = max(
            self._min_timeout, min(timeout, self._max_timeout))
        bridge_idx = generate_bridge_index(
            protocol, 'rabbitmq', request_id)
        self.routing_table.add(
            RoutingEntry(
                pa_n=protocol, pa_s='rabbitmq',
                dt=simulation.client_id,
                sim_type=simulation.type,
                request_id=request_id,
                timeout_seconds=timeout,
                bridge_index=bridge_idx),
            client_id=simulation.client_id,
            simulator=simulation.simulator)
        return bridge_idx, timeout

    @staticmethod
    def _build_outgoing(simulation, bridge_idx):
        """Serialize simulation and inject bridge_index."""
        out = MessageModel(simulation=simulation).model_dump()
        out['simulation']['bridge_index'] = bridge_idx
        return out

    def handle_result_message(self, sender, **kwargs):  # pylint: disable=unused-argument
        """Route a simulation result via the routing table."""
        message = kwargs.get('message', {})
        request_id = message.get('request_id', 'unknown')
        self.routing_table.purge_expired()
        entry = self._validate_result(message, request_id)
        if entry is None:
            return
        routed_kwargs = dict(kwargs)
        routed_msg = dict(message)
        routed_msg['destinations'] = [entry.dt]
        routed_kwargs['message'] = routed_msg
        self._route_result_to_adapter(
            entry.pa_n, sender, **routed_kwargs)
        self._finalize_if_terminal(message, request_id, entry)

    def _validate_result(self, message, request_id):
        """Lookup entry and verify bridge_index; return entry or None."""
        entry = self.routing_table.lookup(request_id)
        if entry is None:
            logger.warning(
                "No routing entry for request_id=%s "
                "— discarding result", request_id)
            return None
        if 'bridge_index' in message and entry.bridge_index:
            if message['bridge_index'] != entry.bridge_index:
                logger.warning(
                    "bridge_index mismatch for request_id=%s "
                    "— discarding result (expected=%s, got=%s)",
                    request_id, entry.bridge_index,
                    message['bridge_index'])
                return None
        return entry

    def _finalize_if_terminal(self, message, request_id, entry):
        """Remove entry and record metrics on terminal status."""
        status = message.get('status', '')
        if status not in _TERMINAL_STATUSES:
            return
        self.routing_table.remove(request_id)
        if entry.pa_n == 'rabbitmq':
            sim_type = message.get(
                'simulation', {}).get('type', 'unknown')
            pm = PerformanceMonitor()
            pm.record_result_sent(
                request_id, entry.pa_n, entry.dt, sim_type)
            pm.finalize_operation(
                request_id, entry.pa_n, entry.dt, sim_type)

    def handle_result_rabbitmq_message(self, sender, **kwargs):
        """Backward-compat alias for handle_result_message."""
        self.handle_result_message(sender, **kwargs)

    def handle_result_unknown_message(self, sender, **kwargs):  # pylint: disable=unused-argument
        """Route unknown-protocol results via routing table."""
        message = kwargs.get('message', {})
        request_id = message.get('request_id', 'unknown')
        entry = self.routing_table.lookup(request_id)
        if entry is not None:
            self.handle_result_message(sender, **kwargs)
            return
        logger.error(
            "Received result with unknown protocol and "
            "no routing entry: %s",
            message.get('error', request_id))

    def _route_result_to_adapter(self, pa_n, sender, **kwargs):
        """Deliver result via RabbitMQ or adapter method."""
        message = kwargs.get('message', {})
        if pa_n == 'rabbitmq':
            self._publish_message(
                message.get('source', 'unknown'), 'result',
                message, exchange='ex.bridge.result',
                protocol='rabbitmq',
                operation_id=message.get('request_id', 'unknown'))
            return
        self._publish_result_adapter(pa_n, sender, **kwargs)

    def _publish_result_adapter(self, pa_n, sender, **kwargs):
        """Invoke the adapter's result delivery method."""
        adapter = self.adapters.get(pa_n)
        method_name = _RESULT_METHOD_FOR_PA.get(pa_n) if adapter else None
        if not adapter:
            logger.error("No adapter for protocol '%s'", pa_n)
            return
        if method_name is None:
            logger.error("No delivery method for '%s'", pa_n)
            return
        method = getattr(adapter, method_name, None)
        if method is None:
            logger.error("Adapter '%s' missing '%s'", pa_n, method_name)
            return
        method(sender, **kwargs)

    def _publish_message(  # pylint: disable=too-many-arguments,too-many-positional-arguments
            self, producer, consumer, message,
            exchange='ex.bridge.output', protocol='unknown',
            operation_id='unknown'):
        """Publish via BridgePublisher and sync connection refs."""
        self._publisher.publish(
            producer, consumer, message,
            exchange=exchange, protocol=protocol,
            operation_id=operation_id)
        self.connection = self._publisher.connection
        self.channel = self._publisher.channel

    def _initialize_rabbitmq_connection(self):
        """Backward-compat wrapper for publisher reconnect."""
        self._publisher._initialize_connection()  # pylint: disable=protected-access
        self.connection = self._publisher.connection
        self.channel = self._publisher.channel

    def _ensure_connection(self):
        """Backward-compat wrapper for publisher ensure_connection."""
        result = self._publisher.ensure_connection()
        self.connection = self._publisher.connection
        self.channel = self._publisher.channel
        return result
