"""Per-request streaming session management for AnyLogic."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils.create_response import create_response
from ..utils.logger import get_logger
from ..utils.performance_monitor import PerformanceMonitor
from .UDPlistener import Listener

logger = get_logger()

_ACTIVE_SESSIONS: Dict[str, "StreamingSession"] = {}
_SESSIONS_LOCK = threading.Lock()


class StreamingSession:
    """Represent a background streaming request handled by a listener thread.

    The session keeps track of the listener, the underlying thread, and the
    resolved simulation file path so callers can stop or inspect the current
    streaming run.
    """

    def __init__(
        self,
        request_id: str,
        listener: Listener,
        thread: threading.Thread,
        sim_file: str,
        file_path: Optional[Path],
    ) -> None:
        """Store state associated with a single streaming simulation request."""
        self.request_id = request_id
        self.listener = listener
        self.thread = thread
        self.sim_file = sim_file
        self.file_path = file_path

    def stop(self) -> None:
        """Stop the listener and wait briefly for the worker thread to finish."""
        self.listener.stop()
        if self.thread.is_alive():
            self.thread.join(timeout=2)


def handle_streaming_simulation(
    msg_dict: Dict[str, Any],
    source: str,
    rabbitmq_manager: Any,
    config: Dict[str, Any],
    response_templates: Dict[str, Any],
) -> None:
    """Start a listener to stream an AnyLogic simulation result.

    Args:
        msg_dict: Incoming RabbitMQ payload already decoded into a dictionary.
        source: Routing key used to return progress and result messages.
        rabbitmq_manager: Abstraction responsible for publishing responses.
        config: Agent configuration containing RabbitMQ and simulation details.
        response_templates: Jinja templates used to build response messages.

    Publishing an error response is preferred over raising when validation or
    environmental checks fail, so callers do not crash the worker process.
    The function only starts a new session when the request identifier is not
    already associated with an active listener.
    """
    perf_monitor = PerformanceMonitor()
    operation_started = False

    data = msg_dict.get('simulation', {}) or {}
    request_id = data.get('request_id')
    sim_file = data.get('file')
    bridge_meta = data.get('bridge_meta', 'unknown')
    sim_type = data.get('type', 'streaming')

    if not request_id or not sim_file:
        error_response = create_response(
            template_type='error',
            sim_file=sim_file or '',
            sim_type='streaming',
            response_templates=response_templates,
            bridge_meta=bridge_meta,
            request_id=request_id or 'unknown',
            error={
                'message': "Missing 'request_id' or 'file' in streaming request",
                'type': 'invalid_request',
            },
        )
        success = rabbitmq_manager.send_result(source, error_response)
        if success:
            perf_monitor.record_result_sent()
        return

    with _SESSIONS_LOCK:
        if request_id in _ACTIVE_SESSIONS:
            logger.warning(
                "Streaming session already active for request %s", request_id)
            return

    sim_config = (config.get('simulation', {}) or {})
    sim_path = sim_config.get('path') or data.get('path')
    expected_file = Path(sim_path).joinpath(
        sim_file).resolve() if sim_path else None

    # Check if the simulation file exists
    if expected_file and not expected_file.exists():
        error_response = create_response(
            template_type='error',
            sim_file=sim_file,
            sim_type=sim_type,
            response_templates=response_templates,
            bridge_meta=bridge_meta,
            request_id=request_id,
            error={
                'message': f"Simulation file '{expected_file}' not found",
                'type': 'missing_file',
            },
        )
        success = rabbitmq_manager.send_result(source, error_response)
        if success:
            perf_monitor.record_result_sent()
        return

    perf_monitor.start_operation(request_id)
    operation_started = True

    listener = Listener(
        config=config,
        destination=source,
        request_id=request_id,
        sim_file=sim_file,
        bridge_meta=bridge_meta,
        sim_type=sim_type,
        on_complete=_build_completion_callback(request_id),
    )
    thread = threading.Thread(
        target=listener.start,
        name=f"anylogic-stream-{request_id}",
        daemon=True,
    )
    thread.start()

    if not listener.wait_until_ready(timeout=5.0):
        listener.stop()
        thread.join(timeout=2)
        error_response = create_response(
            template_type='error',
            sim_file=sim_file,
            sim_type=sim_type,
            response_templates=response_templates,
            bridge_meta=bridge_meta,
            request_id=request_id,
            error={
                'message': 'Streaming listener failed to start',
                'type': 'listener_start_failure',
            },
        )
        success = rabbitmq_manager.send_result(source, error_response)
        if success:
            perf_monitor.record_result_sent()
        if operation_started:
            perf_monitor.complete_operation()
        return

    with _SESSIONS_LOCK:
        _ACTIVE_SESSIONS[request_id] = StreamingSession(
            request_id=request_id,
            listener=listener,
            thread=thread,
            sim_file=sim_file,
            file_path=expected_file,
        )

    perf_monitor.record_anylogic_start()

    status_response = create_response(
        template_type='progress',
        sim_file=sim_file,
        sim_type=sim_type,
        response_templates=response_templates,
        bridge_meta=bridge_meta,
        request_id=request_id,
        percentage=0,
        message='Streaming listener ready',
        data={
            'status': 'listening',
            'host': listener.host,
            'output_port': listener.output_port,
        },
    )
    success = rabbitmq_manager.send_result(source, status_response)
    if success:
        perf_monitor.record_result_sent()
    logger.info(
        "Started streaming listener for %s (request %s) on %s:%s",
        sim_file,
        request_id,
        listener.host,
        listener.output_port,
    )


def _build_completion_callback(request_id: str):
    """Return a callback that marks the session identified by *request_id* done."""

    def _callback(_: str) -> None:
        perf_monitor = PerformanceMonitor()
        perf_monitor.record_simulation_complete()
        perf_monitor.record_anylogic_stop()
        perf_monitor.complete_operation()
        _complete_streaming_session(request_id)

    return _callback


def stop_streaming_session(request_id: str) -> None:
    """Stop and remove the streaming session matching *request_id* if present."""
    with _SESSIONS_LOCK:
        session = _ACTIVE_SESSIONS.pop(request_id, None)
    if session:
        session.stop()
    PerformanceMonitor().complete_operation()


def stop_all_streaming_sessions() -> None:
    """Stop and purge every active streaming session."""
    with _SESSIONS_LOCK:
        sessions = list(_ACTIVE_SESSIONS.values())
        _ACTIVE_SESSIONS.clear()
    for session in sessions:
        session.stop()
    PerformanceMonitor().complete_operation()


def _complete_streaming_session(request_id: str) -> None:
    """Finish a streaming session when the listener signals completion."""
    with _SESSIONS_LOCK:
        session = _ACTIVE_SESSIONS.pop(request_id, None)
    if session and threading.current_thread() is not session.thread:
        session.stop()
    PerformanceMonitor().complete_operation()
