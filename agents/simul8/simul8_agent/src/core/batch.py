"""
batch.py - Simul8 Simulation Batch Processor

This module provides functionality to process Simul8 simulation requests received through
the Connect messaging abstraction layer.
"""

import os
import sys
import time
from typing import Dict, List, Any, Tuple, Optional

import yaml

from ..utils.logger import get_logger
from ..utils.create_response import create_response
from ..comm.interfaces import IMessageBroker
from .simul8_simulator import Simul8Simulator, Simul8SimulationError

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
    
    logger.debug(f"Starting handle_batch_simulation with msg_dict keys: {list(msg_dict.keys())}")
    
    # Initialize performance monitor
    operation_id = msg_dict.get('simulation', {}).get('request_id', 'unknown')
    logger.debug(f"Operation ID: {operation_id}")

    try:
        logger.debug(f"About to record simul8 start")
        
        
        logger.debug(f"Getting simulation data from message")
        data: Dict[str, Any] = msg_dict.get('simulation', {})
        logger.debug(f"Simulation data keys: {list(data.keys())}")
        
        bridge_meta = data.get('bridge_meta', 'unknown')
        request_id = data.get('request_id', 'unknown')
        sim_file = data.get('file')
        
        logger.debug(f"bridge_meta={bridge_meta}, request_id={request_id}, sim_file={sim_file}")
        logger.debug(f"path_simulation={path_simulation}")
        
        if not sim_file:
            raise ValueError("No simulation file specified in request")
        try:
            # Handle Simul8 simulation
            _handle_simulation(data, source, rabbitmq_manager, path_simulation,
                               response_templates, sim_file=sim_file)
        except Simul8SimulationError as e:
            logger.error(f"DEBUG: Simul8 simulation error: {str(e)}")
            raise e
        logger.debug(f"validating simulation data")
        function_name = _validate_simulation_data(data)
        logger.debug(f"Validation complete, function_name={function_name}")

        sim_path = path_simulation
        logger.debug(f"extracting I/O specs")
        inputs, outputs = _extract_io_specs(data)
        logger.debug(f"I/O extraction complete, inputs={inputs}, outputs={outputs}")
        
        logger.debug(f"Starting simulation '{sim_file}' at path '{sim_path}'")
        sim = Simul8Simulator(sim_path, sim_file, function_name)

        logger.debug("Simulator created, about to record startup complete")
        # Record startup complete
                
    except Exception as e:
        logger.error(f"Exception caught in handle_batch_simulation: {type(e).__name__}: {str(e)}")
        logger.error(f"sim_file value at exception: {sim_file}")
        logger.error(f"Exception traceback:", exc_info=True)
        
        # Now call your error handler
        _handle_error(e, sim_file, rabbitmq_manager, source, response_templates)
   
def _handle_simulation(
    data: Dict[str, Any],
    source: str,
    message_broker: IMessageBroker,
    path_simulation: str,
    response_templates: Dict[str, Any],
    sim_file: str
) -> None:
    sim: Optional[Simul8Simulator] = None  # Initialize sim to None

    """Process a Simul8 simulation request."""
    try:
        # Extract run_time from inputs if present
        bridge_meta = data.get('bridge_meta', 'unknown')
        request_id = data.get('request_id', 'unknown')
        inputs, outputs = _extract_io_specs(data)
        run_time = int(inputs.get('run_time', 500))
        
        logger.info("Starting Simul8 simulation '%s'", sim_file)
        sim = Simul8Simulator(run_time=run_time)
        
        # Set the expected outputs from YAML
        sim.expected_outputs = outputs if outputs else {}
        logger.debug(f"Expected outputs set to: {sim.expected_outputs}")

        _send_progress(message_broker, source, sim_file, 0, response_templates)
        
        # Create full file path
        file_path = os.path.join(path_simulation, sim_file) if path_simulation else sim_file
        
        # Run the simulation
        results = sim.run(file_path=file_path, inputs=inputs)
        
        # Get metadata if needed
        metadata = sim.get_metadata() if response_templates.get(
            'success', {}).get('include_metadata', False) else None
        success_response = create_response(
            'success', sim_file, 'batch', response_templates,
            outputs=results, metadata=metadata, bridge_meta=bridge_meta,
            request_id=request_id
        )
        _send_response(message_broker, source, success_response)
        logger.info("Simul8 simulation '%s' completed successfully", sim_file)
    finally:
        # Only cleanup if sim was actually created
        if sim is not None:
            try:
                sim.cleanup()
                logger.debug("Simulator cleanup completed")
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
        
        
        
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
    # Filter out run_time and other non-CSV parameters
    filtered_inputs = {k: v for k, v in inputs.items() if k not in ['run_time', 'runtime']}
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
