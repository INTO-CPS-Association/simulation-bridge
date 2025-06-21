"""
batch.py - Simul8 Simulation Batch Processor

This module provides functionality to process Simul8 simulation requests received through
the Connect messaging abstraction layer.
"""

import sys
import time
from typing import Dict, List, Any, Tuple, Optional

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
    """
    Handle a batch simulation request.

    Args:
        msg_dict (Dict[str, Any]): The message dictionary
        source (str): The source of the message
        rabbitmq_manager (IMessageBroker): The RabbitMQ manager instance
        path_simulation (str): Path to the simulation files
        response_templates (Dict[str, Any]): Response templates
    """
    # Initialize performance monitor
    performance_monitor = PerformanceMonitor()
    operation_id = msg_dict.get('simulation', {}).get('request_id', 'unknown')
    performance_monitor.start_operation(operation_id)

    try:
        # Record Simul8 start
        performance_monitor.record_simul8_start()

        data: Dict[str, Any] = msg_dict.get('simulation', {})
        bridge_meta = data.get('bridge_meta', 'unknown')
        request_id = data.get('request_id', 'unknown')
        sim_file = data.get('file')
        function_name = _validate_simulation_data(data)
        sim_path = path_simulation
        inputs, outputs = _extract_io_specs(data)
        logger.info("Starting simulation '%s'", sim_file)
        sim = Simul8Simulator(sim_path, sim_file, function_name, run_time=200)
        # Record simul8 startup complete
        performance_monitor.record_simul8_startup_complete()
        _send_progress(rabbitmq_manager,
                       source,
                       sim_file,
                       0,
                       response_templates,
                       bridge_meta,
                       request_id)
        try:
            # Handle Simul8 simulation
            _handle_simulation(data, source, rabbitmq_manager, path_simulation,
                               response_templates, function_name)
        finally:
            sim.cleanup()
        
        results = sim.run(inputs, outputs)
        metadata = _get_metadata(sim) if response_templates.get(
            'success', {}).get('include_metadata', False) else None
        # Record simulation complete
        performance_monitor.record_simulation_complete()
        # Record Simul8 stop
        performance_monitor.record_matlab_stop()
        # Create and send success response
        success_response = create_response(
            'success', sim_file, 'batch', response_templates,
            outputs=results, metadata=metadata, bridge_meta=bridge_meta,
            request_id=request_id
        )

        # Send result and record it
        if rabbitmq_manager.send_result(source, success_response):
            performance_monitor.record_result_sent()

        logger.info("Simulation '%s' completed successfully", sim_file)

    except Exception as e:  # pylint: disable=broad-except
        _handle_error(e, sim_file, rabbitmq_manager, source, response_templates)
    finally:
        # Always complete the operation to record metrics
        performance_monitor.complete_operation()
        if 'sim' in locals():
            sim.close()

def _handle_simulation(
    data: Dict[str, Any],
    source: str,
    message_broker: IMessageBroker,
    path_simulation: str,
    response_templates: Dict[str, Any],
    sim_file: str
) -> None:
    """Process a Simul8 simulation request."""
    sim = None
    try:
        run_time = data.get('run_time')
        inputs, outputs = _extract_io_specs(data)
        
        print(f"DEBUG: Extracted inputs: {inputs}")
        print(f"DEBUG: Extracted outputs: {outputs}")
        
        logger.info("Starting Simul8 simulation '%s'", sim_file)
        sim = Simul8Simulator(run_time=run_time)
        
        # Set the expected outputs from YAML
        sim.expected_outputs = outputs if outputs else {}
        print(f"DEBUG: Set expected outputs on simulator: {sim.expected_outputs}")
        
        _send_progress(message_broker, source, sim_file, 25, response_templates)
        
        # Create full file path
        file_path = f"{path_simulation}/{sim_file}" if path_simulation else sim_file
        
        # Run the simulation
        results = sim.run(file_path=file_path, inputs=inputs)
        
        # Get metadata if needed
        metadata = sim.get_metadata() if response_templates.get(
            'success', {}).get('include_metadata', False) else None
        success_response = create_response(
            'success', sim_file, 'batch', response_templates,
            outputs=results, metadata=metadata
        )
        _send_response(message_broker, source, success_response)
        logger.info("Simul8 simulation '%s' completed successfully", sim_file)
    finally:
        if sim:
            print("CLEANING UP")
            sim.cleanup()
def _validate_simulation_data(
        data: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Validate and extract simulation parameters."""
    sim_file = data.get('file')
    if not sim_file:
        raise ValueError("Missing 'file' in simulation config")
    return data.get('function_name')


def _extract_io_specs(data: Dict[str, Any]
                      ) -> Tuple[Dict[str, Any], List[str]]:
    """Extract input and output specifications from data."""
    inputs = data.get('inputs', {})
    outputs = data.get('outputs', [])
    if not outputs:
        raise ValueError("No outputs specified in simulation config")
    return inputs, outputs




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
