"""
batch.py - MATLAB Simulation Batch Processor

This module provides functionality to process MATLAB simulation requests received through
a message queue system (RabbitMQ). It handles batch simulation jobs by:
1. Starting a MATLAB engine
2. Running specified simulation files with provided inputs
3. Collecting and returning simulation outputs via the message queue
4. Providing proper error handling and logging

Part of the simulation service infrastructure that enables distributed
MATLAB computational workloads.
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, Union, List, Optional, Any, Tuple

import psutil
import yaml
import matlab.engine

from ..utils.logger import get_logger
from ..utils.config_loader import load_config
from ..utils.create_response import create_response
from ..core.rabbitmq_manager import RabbitMQManager

# Configure logger
logger = get_logger()

# Load configuration
config: Dict[str, Any] = load_config()

# Response templates
response_templates: Dict[str, Any] = config.get('response_templates', {})


class MatlabSimulationError(Exception):
    """Custom exception for MATLAB simulation errors."""


class MatlabSimulator:
    """
    Manages the lifecycle of a MATLAB simulation with proper resource management,
    error handling and type conversions.
    """

    def __init__(self, path: str, file: str, function_name: Optional[str] = None) -> None:
        """
        Initialize a MATLAB simulator.

        Args:
            path: Directory path containing the simulation files
            file: Name of the main simulation file
            function_name: Name of the function to call (defaults to file name without extension)
        """
        self.sim_path: Path = Path(path).resolve()
        self.sim_file: str = file
        self.function_name: str = function_name or os.path.splitext(file)[0]
        self.eng: Optional[matlab.engine.MatlabEngine] = None
        self.start_time: Optional[float] = None
        self._validate()

    def _validate(self) -> None:
        """Validate the simulation path and file."""
        if not self.sim_path.is_dir():
            raise FileNotFoundError(f"Simulation directory not found: {self.sim_path}")

        if not (self.sim_path / self.sim_file).exists():
            raise FileNotFoundError(f"Simulation file '{self.sim_file}' not \
                found at {self.sim_path}")

    def start(self) -> None:
        """Start the MATLAB engine and prepare for simulation."""
        logger.debug("Starting MATLAB engine for simulation: %s", self.sim_file)
        try:
            self.start_time = time.time()
            self.eng = matlab.engine.start_matlab()
            self.eng.eval("clear; clc;", nargout=0)
            self.eng.addpath(str(self.sim_path), nargout=0)
            logger.debug("MATLAB engine started successfully")
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Failed to start MATLAB engine: %s", str(e))
            raise MatlabSimulationError(f"Failed to start MATLAB engine: {str(e)}") from e

    def run(self, inputs: Dict[str, Any], outputs: List[str]) -> Dict[str, Any]:
        """Run the MATLAB simulation and return the results."""
        if not self.eng:
            raise MatlabSimulationError("MATLAB engine is not started")

        try:
            logger.debug("Running simulation %s with inputs: %s", self.function_name, inputs)
            self.eng.eval("clear variables;", nargout=0)
            matlab_args: List[Any] = [self._to_matlab(v) for v in inputs.values()]
            result: Union[Any, Tuple[Any, ...]] = self.eng.feval(
                self.function_name, *matlab_args, nargout=len(outputs))

            return self._process_results(result, outputs)

        except Exception as e:  # pylint: disable=broad-except
            msg = f"Simulation error: {str(e)}"
            logger.error(msg, exc_info=True)
            raise MatlabSimulationError(msg) from e

    def _process_results(self,
                         result: Union[Any, Tuple[Any, ...]],
                         outputs: List[str]) -> Dict[str, Any]:
        """Process MATLAB results into Python types."""
        if len(outputs) == 1:
            return {outputs[0]: self._from_matlab(result)}
        return {name: self._from_matlab(result[i]) for i, name in enumerate(outputs)}

    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata about the simulation execution."""
        metadata: Dict[str, Any] = {}
        if self.start_time:
            metadata['execution_time'] = time.time() - self.start_time

        process = psutil.Process(os.getpid())
        metadata['memory_usage'] = process.memory_info().rss / (1024 * 1024)  # MB

        if self.eng:
            try:
                metadata['matlab_version'] = self.eng.eval("version", nargout=1)
            except Exception as e:
                logger.warning("Error retrieving MATLAB version: %s", str(e))
        return metadata

    @staticmethod
    def _to_matlab(value: Any) -> Any:
        """Convert Python values to MATLAB types."""
        if isinstance(value, (list, tuple)):
            if not value:
                return matlab.double([])
            return matlab.double(
                list(value)
                if isinstance(value[0],
                              (list, tuple))
                else [list(value)])
        if isinstance(value, (int, float)):
            return float(value)
        return value

    @staticmethod
    def _from_matlab(value: Any) -> Any:
        """Convert MATLAB types back to Python types."""
        if isinstance(value, matlab.double):
            size = value.size
            if size == (1, 1):
                return float(value[0][0])
            if size[0] == 1 or size[1] == 1:
                return [value[i][0] for i in range(size[0])] if size[0] > 1 else value[0]
            return [[value[i][j] for j in range(size[1])] for i in range(size[0])]
        return value

    def close(self) -> None:
        """Close the MATLAB engine and release resources."""
        if self.eng:
            try:
                self.eng.quit()
                logger.debug("MATLAB engine closed successfully")
            except Exception as e:
                logger.warning("Error closing MATLAB engine: %s", str(e))
            finally:
                self.eng = None


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
            logger.warning("MATLAB start failed (attempt %s/%s). Retrying...", attempt, max_retries)
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
    logger.error("Simulation '%s' failed: %s", sim_file, str(error), exc_info=True)
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
