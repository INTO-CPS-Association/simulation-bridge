"""
batch_processor.py - MATLAB Simulation Batch Processor

This module provides functionality to process MATLAB simulation requests received through
a message queue system (RabbitMQ).
"""

import sys
import time
from typing import Dict, List, Any, Tuple, Optional

import yaml

from ..utils.logger import get_logger
from ..utils.config_loader import load_config
from ..utils.create_response import create_response
from ..core.rabbitmq_manager import RabbitMQManager
from .matlab_simulator import MatlabSimulator, MatlabSimulationError

# Configure logger
logger = get_logger()

# Load configuration
config: Dict[str, Any] = load_config()

# Response templates
response_templates: Dict[str, Any] = config.get('response_templates', {})


def handle_batch_simulation(
    parsed_data: Dict[str, Any],
    source: str,
    rabbitmq_manager: RabbitMQManager
) -> None:
    """Process a batch simulation request and send results via RabbitMQ."""
    data: Dict[str, Any] = parsed_data.get('simulation', {})
    sim_file = data.get('file')

    try:
        sim_path, function_name = _validate_simulation_data(data)
        inputs, outputs = _extract_io_specs(data)
        sim = MatlabSimulator(sim_path, sim_file, function_name)
        _send_progress(rabbitmq_manager, source, sim_file, 0)

        _start_matlab_with_retry(sim)
        _send_progress(rabbitmq_manager, source, sim_file, 50)

        results = sim.run(inputs, outputs)
        metadata = _get_metadata(sim) \
            if response_templates.get('success', {}).get('include_metadata', False) \
            else None

        success_response = create_response(
            'success', sim_file, 'batch', response_templates,
            outputs=results, metadata=metadata
        )
        _send_response(rabbitmq_manager, source, success_response)
        logger.info("Simulation '%s' completed successfully", sim_file)

    except Exception as e:  # pylint: disable=broad-except
        _handle_error(e, sim_file, rabbitmq_manager, source)
    finally:
        if 'sim' in locals():
            sim.close()


def _validate_simulation_data(data: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Validate and extract simulation parameters."""
    sim_path = config['simulation'].get('path')
    sim_file = data.get('file')
    if not sim_path or not sim_file:
        raise ValueError("Missing 'path' or 'file' in simulation config")
    return sim_path, data.get('function_name')


def _extract_io_specs(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Extract input and output specifications from data."""
    inputs = data.get('inputs', {})
    outputs = data.get('outputs', [])
    if not outputs:
        raise ValueError("No outputs specified in simulation config")
    return inputs, outputs


def _start_matlab_with_retry(sim: MatlabSimulator, max_retries: int = 3) -> None:
    """Attempt to start MATLAB engine with retries."""
    for attempt in range(1, max_retries + 1):
        try:
            sim.start()
            return
        except MatlabSimulationError:
            if attempt == max_retries:
                raise
            logger.warning(
                "MATLAB start failed (attempt %s/%s). Retrying...", attempt, max_retries)
            time.sleep(1)


def _send_progress(manager: RabbitMQManager, source: str, sim_file: str, percentage: int) -> None:
    """Send progress update if configured."""
    if response_templates.get('progress', {}).get('include_percentage', False):
        progress_response = create_response(
            'progress', sim_file, 'batch', response_templates, percentage=percentage
        )
        _send_response(manager, source, progress_response)


def _get_metadata(sim: MatlabSimulator) -> Dict[str, Any]:
    """Retrieve simulation metadata."""
    return sim.get_metadata()


def _send_response(manager: RabbitMQManager, source: str, response: Dict[str, Any]) -> None:
    """Send response through RabbitMQ."""
    print(yaml.dump(response))
    manager.send_result(source, response)


def _handle_error(error: Exception,
                  sim_file: Optional[str],
                  manager: RabbitMQManager,
                  source: str) -> None:
    """Handle errors and send error response."""
    logger.error("Simulation '%s' failed: %s",
                 sim_file, str(error), exc_info=True)
    error_type = _determine_error_type(error)
    error_response = create_response(
        'error', sim_file or "unknown", 'batch', response_templates,
        error={'message': str(error), 'type': error_type,
               'traceback': sys.exc_info()
               if response_templates.get('error', {}).get('include_stacktrace', False)
               else None}
    )
    _send_response(manager, source, error_response)


def _determine_error_type(error: Exception) -> str:
    """Map Python exceptions to error types."""
    if isinstance(error, FileNotFoundError):
        return 'missing_file'
    if isinstance(error, MatlabSimulationError):
        return 'matlab_start_failure' if 'MATLAB engine' in str(error) else 'execution_error'
    if isinstance(error, TimeoutError):
        return 'timeout'
    if isinstance(error, ValueError):
        return 'invalid_config'
    return 'execution_error'
