"""Batch processor for Python Agent CLI execution."""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..comm.interfaces import IMessageBroker
from ..utils.create_response import create_response
from ..utils.logger import get_logger
from ..utils.performance_monitor import PerformanceMonitor
from .python_simulator import PythonSimulationError, PythonSimulator

logger = get_logger()


def handle_batch_simulation(
    msg_dict: Dict[str, Any],
    source: str,
    rabbitmq_manager: IMessageBroker,
    path_simulation: str,
    response_templates: Dict[str, Any],
) -> None:
    """Handle a batch request by executing the configured script/program."""
    sim_file: Optional[str] = None
    operation_id = msg_dict.get("simulation", {}).get("request_id", "unknown")

    performance_monitor = PerformanceMonitor()
    performance_monitor.start_operation(operation_id)

    try:
        performance_monitor.record_python_start()

        data = msg_dict.get("simulation", {})
        bridge_meta = data.get("bridge_meta", "unknown")
        request_id = data.get("request_id", "unknown")
        sim_file = _validate_simulation_data(data, path_simulation)
        inputs, outputs = _extract_io_specs(data)

        logger.info("Starting Python command '%s'", sim_file)
        simulator = PythonSimulator(timeout=data.get("timeout"))
        performance_monitor.record_python_startup_complete()

        _send_progress(
            rabbitmq_manager,
            source,
            sim_file,
            0,
            response_templates,
            bridge_meta,
            request_id,
        )

        sim_result = simulator.run(Path(path_simulation) / sim_file, inputs, outputs)
        metadata = simulator.get_metadata() if response_templates.get(
            "success", {}
        ).get("include_metadata", False) else None

        performance_monitor.record_simulation_complete()
        performance_monitor.record_python_stop()

        success_response = create_response(
            "success",
            sim_file,
            "batch",
            response_templates,
            outputs=sim_result,
            metadata=metadata,
            bridge_meta=bridge_meta,
            request_id=request_id,
        )
        if rabbitmq_manager.send_result(source, success_response):
            performance_monitor.record_result_sent()

        logger.info("Python command '%s' completed successfully", sim_file)

    except Exception as error:  # pylint: disable=broad-except
        logger.error("Exception caught in handle_batch_simulation: %s", error)
        _handle_error(error, sim_file, rabbitmq_manager, source, response_templates)
    finally:
        performance_monitor.complete_operation()


def _validate_simulation_data(data: Dict[str, Any], path_simulation: str) -> str:
    sim_file = data.get("file")
    if not sim_file:
        raise ValueError("Missing 'file' in simulation config")

    sim_file_path = Path(path_simulation) / sim_file
    if not sim_file_path.is_file():
        raise FileNotFoundError(f"Simulation file {sim_file_path} not found")
    return sim_file


def _extract_io_specs(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    inputs = data.get("inputs", {})
    outputs = data.get("outputs", [])
    return inputs, outputs


def _send_progress(
    broker: IMessageBroker,
    source: str,
    sim_file: str,
    percentage: int,
    response_templates: Dict[str, Any],
    bridge_meta: str,
    request_id: str,
) -> None:
    if response_templates.get("progress", {}).get("include_percentage", False):
        progress_response = create_response(
            "progress",
            sim_file,
            "batch",
            response_templates,
            percentage=percentage,
            bridge_meta=bridge_meta,
            request_id=request_id,
        )
        broker.send_result(source, progress_response)


def _handle_error(
    error: Exception,
    sim_file: Optional[str],
    broker: IMessageBroker,
    source: str,
    response_templates: Dict[str, Any],
) -> None:
    error_type = _determine_error_type(error)
    error_response = create_response(
        "error",
        sim_file or "unknown",
        "batch",
        response_templates,
        error={
            "message": str(error),
            "type": error_type,
            "traceback": sys.exc_info()
            if response_templates.get("error", {}).get("include_stacktrace", False)
            else None,
        },
        bridge_meta=response_templates.get("bridge_meta", "unknown"),
        request_id=response_templates.get("request_id", "unknown"),
    )
    broker.send_result(source, error_response)


def _determine_error_type(error: Exception) -> str:
    if isinstance(error, FileNotFoundError):
        return "missing_file"
    if isinstance(error, PythonSimulationError):
        return "execution_error"
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, ValueError):
        return "invalid_config"
    return "execution_error"
