"""
batch.py - Simul8 Simulation Batch Processor

This module provides functionality to process Simul8 simulation requests received through
the Connect messaging abstraction layer.
"""

import os
import sys
import time
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path

import yaml

from ..utils.logger import get_logger
from ..utils.create_response import create_response
from ..comm.interfaces import IMessageBroker
from .simul8_simulator import Simul8Simulator, Simul8SimulationError
from ..utils.performance_monitor import PerformanceMonitor

# Configure logger
logger = get_logger()


def handle_batch_simulation(
    msg_dict: Dict[str, Any],
    source: str,
    rabbitmq_manager: IMessageBroker,
    path_simulation: str,
    response_templates: Dict[str, Any]
) -> None:
    """Handle a batch simulation request."""
    sim_file: Optional[str] = None  # Initialize this first!


    # Initialize performance monitor
    operation_id = msg_dict.get('simulation', {}).get('request_id', 'unknown')
    logger.debug(f"Operation ID: {operation_id}")

    performance_monitor = PerformanceMonitor()
    performance_monitor.start_operation(operation_id)
    try:
        performance_monitor.record_matlab_start()

        data: Dict[str, Any] = msg_dict.get('simulation', {})
        logger.debug(f"Simulation data keys: {list(data.keys())}")

        bridge_meta = data.get('bridge_meta', 'unknown')
        request_id = data.get('request_id', 'unknown')
        sim_file = _validate_simulation_data(data, path_simulation)

        logger.debug(
            f"bridge_meta={bridge_meta}, request_id={request_id}, sim_file={sim_file}")
        logger.debug(f"path_simulation={path_simulation}")

        if not sim_file:
            raise ValueError("No simulation file specified in request")

        inputs, outputs = _extract_io_specs(data)
        logger.debug(f"I/O extraction complete, inputs={inputs}, outputs={outputs}")

        sim: Optional[Simul8Simulator] = None
        try:
            run_time = int(inputs.get('run_time', 500))
            logger.info("Starting Simul8 simulation '%s'", sim_file)
            sim = Simul8Simulator(run_time=run_time)

            # Set expected outputs for the simulator instance
            sim.expected_outputs = outputs
            logger.debug(f"Expected outputs set to: {sim.expected_outputs}")

            _send_progress(rabbitmq_manager, source, sim_file, 0, response_templates)

            sim_path = Path(path_simulation)
            sim_file_path = sim_path / sim_file
        
            results = sim.run(file_path=sim_file_path, inputs=inputs, outputs=outputs)

            metadata = sim.get_metadata() if response_templates.get('success', {}).get('include_metadata', False) else None
            success_response = create_response(
                'success', sim_file, 'batch', response_templates,
                outputs=results, metadata=metadata, bridge_meta=bridge_meta,
                request_id=request_id
            )
            _send_response(rabbitmq_manager, source, success_response)
            logger.info("Simul8 simulation '%s' completed successfully", sim_file)
        finally:
            if sim is not None:
                try:
                    sim.cleanup()
                    logger.debug("Simulator cleanup completed")
                except Exception as cleanup_error:
                    logger.error(f"Error during cleanup: {cleanup_error}")

    except Exception as e:
        logger.error(
            f"Exception caught in handle_batch_simulation: {
                type(e).__name__}: {
                str(e)}"
                )
        logger.error(f"sim_file value at exception: {sim_file}")
        logger.error(f"Exception traceback:", exc_info=True)

        # Now call your error handler
        _handle_error(e, sim_file, rabbitmq_manager, source, response_templates)
        



def _validate_simulation_data(
        data: Dict[str, Any], path_simulation: str) -> str:
    """Validate and extract simulation file name for Simul8."""
    sim_file = data.get('file')
    if not sim_file:
        raise ValueError("Missing 'file' in simulation config")
   
    sim_path = Path(path_simulation)
    sim_file_path = sim_path / sim_file
    if not sim_file_path.exists():
        raise FileNotFoundError(f"Simulation file '{sim_file_path}' not found")
    return sim_file


def _extract_io_specs(data: Dict[str, Any]
                      ) -> Tuple[Dict[str, Any], List[str]]:
    """Extract input and output specifications from data."""
    inputs = data.get('inputs', {})
    # Only filter out 'run_time', not 'runtime'
    filtered_inputs = {k: v for k, v in inputs.items() if k != 'run_time'}
    outputs = data.get('outputs', [])

    if not outputs:
        raise ValueError("No outputs specified in simulation config")
    return filtered_inputs, outputs


def _send_progress(
        broker: IMessageBroker,
        source: str,
        sim_file: str,
        percentage: int,
        response_templates: Dict,
        bridge_meta: str = 'unknown',
        request_id: str = 'unknown'
) -> None:
    """Send progress update if configured."""
    if response_templates.get('progress', {}).get('include_percentage', False):
        progress_response = create_response(
            'progress',
            sim_file,
            'batch',
            response_templates,
            percentage=percentage,
            bridge_meta=bridge_meta,
            request_id=request_id)
        broker.send_result(source, progress_response)


def _get_metadata(sim: Simul8Simulator) -> Dict[str, Any]:
    """Retrieve simulation metadata."""
    return sim.get_metadata()


def _send_response(broker: IMessageBroker, source: str,
                   response: Dict[str, Any]) -> None:
    """Send response through message broker."""
    logger.debug(yaml.dump(response))
    broker.send_result(source, response)


def _handle_error(error: Exception,
                  sim_file: Optional[str],
                  broker: IMessageBroker,
                  source: str,
                  response_templates: Dict
                  ) -> None:
    """Handle errors and send error response."""
    error_type = _determine_error_type(error)
    error_response = create_response(
        'error',
        sim_file or "unknown",
        'batch',
        response_templates,
        error={
            'message': str(error),
            'type': error_type,
            'traceback': sys.exc_info() if response_templates.get(
                'error',
                {}).get(
                'include_stacktrace',
                False) else None},
        bridge_meta=response_templates.get('bridge_meta', 'unknown'),
        request_id=response_templates.get('request_id', 'unknown')
    )
    _send_response(broker, source, error_response)


def _determine_error_type(error: Exception) -> str:
    """Map Python exceptions to error types."""
    if isinstance(error, FileNotFoundError):
        return 'missing_file'
    if isinstance(error, Simul8SimulationError):
        return 'simul8_start_failure' if 'simul8 engine' in str(
            error) else 'execution_error'
    if isinstance(error, TimeoutError):
        return 'timeout'
    if isinstance(error, ValueError):
        return 'invalid_config'
    return 'execution_error'
