"""Interactive AnyLogic simulation bridge."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, Optional

from ..comm.rabbitmq.rabbitmq_manager import RabbitMQManager
from ..utils.create_response import create_response
from ..utils.logger import get_logger
from ..utils.performance_monitor import PerformanceMonitor
from .UDPwriter import Writer
from .UDPlistener import Listener

logger = get_logger()

# Session management for interactive runs
_ACTIVE_SESSIONS: Dict[str, "InteractiveSession"] = {}
_SESSIONS_LOCK = threading.Lock()


class InteractiveSession:
    """Represent a background interactive request handled by writer and listener threads."""

    def __init__(
        self,
        request_id: str,
        writer: Writer,
        writer_thread: threading.Thread,
        listener: Listener,
        listener_thread: threading.Thread,
        sim_file: str,
        file_path: Optional[Path],
    ) -> None:
        self.request_id = request_id
        self.writer = writer
        self.writer_thread = writer_thread
        self.listener = listener
        self.listener_thread = listener_thread
        self.sim_file = sim_file
        self.file_path = file_path

    def stop(self) -> None:
        self.writer.stop()
        self.listener.stop()
        if self.writer_thread.is_alive():
            self.writer_thread.join(timeout=2)
        if self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2)


def handle_interactive_simulation(
    msg_dict: Dict[str, Any],
    source: str,
    rabbitmq_manager: RabbitMQManager,
    config: Dict[str, Any],
    response_templates: Dict[str, Any],
) -> None:
    """Start writer and listener to interactively send and receive messages with AnyLogic simulation."""
    perf_monitor = PerformanceMonitor()
    operation_started = False

    data = msg_dict.get('simulation', {}) or {}
    request_id = data.get('request_id')
    sim_file = data.get('file')
    bridge_meta = data.get('bridge_meta', 'unknown')
    sim_type = data.get('type', 'interactive')
    stream_key = _extract_stream_key(data)

    if not request_id or not sim_file:
        error_response = create_response(
            template_type='error',
            sim_file=sim_file or '',
            sim_type='interactive',
            response_templates=response_templates,
            bridge_meta=bridge_meta,
            request_id=request_id or 'unknown',
            error={
                'message': "Missing 'request_id' or 'file' in interactive request",
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
                "Interactive session already active for request %s", request_id)
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

    # Start the Writer (sender)
    writer = Writer(
        config=config,
        destination=source,
        request_id=request_id,
        sim_file=sim_file,
        bridge_meta=bridge_meta,
        sim_type=sim_type,
        stream_key=stream_key,
        on_complete=_build_completion_callback(request_id),
    )
    writer_thread = threading.Thread(
        target=writer.start,
        name=f"anylogic-interactive-writer-{request_id}",
        daemon=True,
    )
    writer_thread.start()

    # Start the Listener (receiver)
    listener = Listener(
        config=config,
        destination=source,
        request_id=request_id,
        sim_file=sim_file,
        bridge_meta=bridge_meta,
        sim_type=sim_type,
        on_complete=_build_completion_callback(request_id),
    )
    listener_thread = threading.Thread(
        target=listener.start,
        name=f"anylogic-interactive-listener-{request_id}",
        daemon=True,
    )
    listener_thread.start()

    # Wait for both to be ready
    if not _wait_for_ready(
        writer,
        listener,
        writer_thread,
        listener_thread,
        source,
        rabbitmq_manager,
        sim_file,
        sim_type,
        response_templates,
        bridge_meta,
        request_id,
        perf_monitor,
    ):
        if operation_started:
            perf_monitor.complete_operation()
        return

    with _SESSIONS_LOCK:
        _ACTIVE_SESSIONS[request_id] = InteractiveSession(
            request_id=request_id,
            writer=writer,
            writer_thread=writer_thread,
            listener=listener,
            listener_thread=listener_thread,
            sim_file=sim_file,
            file_path=expected_file,
        )

    perf_monitor.record_matlab_start()

    status_response = create_response(
        template_type='progress',
        sim_file=sim_file,
        sim_type=sim_type,
        response_templates=response_templates,
        bridge_meta=bridge_meta,
        request_id=request_id,
        percentage=0,
        message='Interactive writer and listener ready',
        data={
            'status': 'ready',
            'writer_ip': writer.host,
            'writer_port': writer.input_port,
            'listener_host': listener.host,
            'listener_port': listener.output_port,
        },
    )
    success = rabbitmq_manager.send_result(source, status_response)
    if success:
        perf_monitor.record_result_sent()
    logger.info(
        "Started interactive writer and listener for %s (request %s) on writer %s:%s, listener %s:%s",
        sim_file,
        request_id,
        writer.host,
        writer.input_port,
        listener.host,
        listener.output_port,
    )


def _extract_stream_key(data: Dict[str, Any]) -> Optional[str]:
    """Extract stream_key from data, checking multiple locations."""
    stream_key = data.get('inputs', {}).get('stream_key')
    if not stream_key:
        stream_source = data.get('inputs', {}).get('stream_source')
        if stream_source:
            stream_key = stream_source.replace("rabbitmq://", "")
    return stream_key


def _wait_for_ready(
    writer: Writer,
    listener: Listener,
    writer_thread: threading.Thread,
    listener_thread: threading.Thread,
    source: str,
    rabbitmq_manager: RabbitMQManager,
    sim_file: str,
    sim_type: str,
    response_templates: Dict[str, Any],
    bridge_meta: str,
    request_id: str,
    perf_monitor: PerformanceMonitor,
) -> bool:
    """Wait for writer and listener to be ready. Returns True if successful."""
    if not writer.wait_until_ready(
            timeout=5.0) or not listener.wait_until_ready(timeout=5.0):
        writer.stop()
        listener.stop()
        writer_thread.join(timeout=2)
        listener_thread.join(timeout=2)
        error_response = create_response(
            template_type='error',
            sim_file=sim_file,
            sim_type=sim_type,
            response_templates=response_templates,
            bridge_meta=bridge_meta,
            request_id=request_id,
            error={
                'message': 'Interactive writer or listener failed to start',
                'type': 'start_failure',
            },
        )
        success = rabbitmq_manager.send_result(source, error_response)
        if success:
            perf_monitor.record_result_sent()
        return False
    return True


def _build_completion_callback(request_id: str):
    """Return a callback that marks the session identified by *request_id* done."""

    def _callback(_: str) -> None:
        perf_monitor = PerformanceMonitor()
        perf_monitor.record_simulation_complete()
        perf_monitor.record_matlab_stop()
        perf_monitor.complete_operation()
        _complete_interactive_session(request_id)

    return _callback


def stop_interactive_session(request_id: str) -> None:
    """Stop and remove the interactive session matching *request_id* if present."""
    with _SESSIONS_LOCK:
        session = _ACTIVE_SESSIONS.pop(request_id, None)
    if session:
        session.stop()
    PerformanceMonitor().complete_operation()


def stop_all_interactive_sessions() -> None:
    """Stop and purge every active interactive session."""
    with _SESSIONS_LOCK:
        sessions = list(_ACTIVE_SESSIONS.values())
        _ACTIVE_SESSIONS.clear()
    for session in sessions:
        session.stop()
    PerformanceMonitor().complete_operation()


def _complete_interactive_session(request_id: str) -> None:
    """Finish an interactive session when the writer or listener signals completion."""
    with _SESSIONS_LOCK:
        session = _ACTIVE_SESSIONS.pop(request_id, None)
    if session and threading.current_thread(
    ) is not session.writer_thread and threading.current_thread() is not session.listener_thread:
        session.stop()
    PerformanceMonitor().complete_operation()
