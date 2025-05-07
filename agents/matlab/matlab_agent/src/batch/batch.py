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

import yaml
import os
import time
import sys
import platform
import psutil
from pathlib import Path
from typing import Dict, Union, List, Optional, Any, Tuple
from datetime import datetime
import matlab.engine
from yaml import SafeLoader, SafeDumper
from ..utils.logger import get_logger
from ..utils.config_loader import load_config
from ..core.rabbitmq_manager import RabbitMQManager

# Configure logger
logger = get_logger()

# Load configuration
config: Dict[str, Any] = load_config()

# Response templates
response_templates: Dict[str, Any] = config.get('response_templates', {})


class MatlabSimulationError(Exception):
    """Custom exception for MATLAB simulation errors."""
    pass


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
        """
        Validate the simulation path and file.
        
        Raises:
            FileNotFoundError: If the simulation file does not exist
        """
        if not self.sim_path.is_dir():
            raise FileNotFoundError(f"Simulation directory not found: {self.sim_path}")
            
        if not (self.sim_path / self.sim_file).exists():
            raise FileNotFoundError(f"Simulation file '{self.sim_file}' not found at {self.sim_path}")

    def start(self) -> None:
        """
        Start the MATLAB engine and prepare for simulation.
        
        Raises:
            MatlabSimulationError: If MATLAB engine fails to start
        """
        logger.debug(f"Starting MATLAB engine for simulation: {self.sim_file}")
        try:
            self.start_time = time.time()
            self.eng = matlab.engine.start_matlab()
            self.eng.eval("clear; clc;", nargout=0)
            self.eng.addpath(str(self.sim_path), nargout=0)
            logger.debug("MATLAB engine started successfully")
        except Exception as e:
            logger.error(f"Failed to start MATLAB engine: {str(e)}")
            raise MatlabSimulationError(f"Failed to start MATLAB engine: {str(e)}") from e

    def run(self,
            inputs: Dict[str, Any],
            outputs: List[str]
    ) -> Dict[str, Any]:
        """
        Run the MATLAB simulation and return the results.
        
        Args:
            inputs: Dictionary of input parameter names to values
            outputs: List of output parameter names to return
            
        Returns:
            Dictionary mapping output names to their computed values
            
        Raises:
            MatlabSimulationError: If MATLAB engine is not started or simulation fails
        """
        if not self.eng:
            raise MatlabSimulationError("MATLAB engine is not started")
            
        try:
            logger.debug(f"Running simulation {self.function_name} with inputs: {inputs}")
            self.eng.eval("clear variables;", nargout=0)
            
            # Convert inputs to MATLAB types
            matlab_args: List[Any] = [self._to_matlab(v) for v in inputs.values()]
            
            # Run the MATLAB function
            result: Union[Any, Tuple[Any, ...]] = self.eng.feval(self.function_name, *matlab_args, nargout=len(outputs))
            
            # Convert the results back to Python types
            if len(outputs) == 1:
                # Handle the case where there's only one output
                return {outputs[0]: self._from_matlab(result)}
            else:
                # Handle multiple outputs
                return {name: self._from_matlab(result[i]) for i, name in enumerate(outputs)}
                
        except matlab.engine.MatlabExecutionError as e:
            msg = f"MATLAB execution failed: {str(e)}"
            logger.error(msg)
            raise MatlabSimulationError(msg) from e
        except Exception as e:
            msg = f"Simulation error: {str(e)}"
            logger.error(msg, exc_info=True)
            raise MatlabSimulationError(msg) from e

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the simulation execution.
        
        Returns:
            Dictionary containing metadata
        """
        metadata: Dict[str, Any] = {}
        
        # Add execution time if available
        if self.start_time:
            metadata['execution_time'] = time.time() - self.start_time
        
        # Get memory usage
        process = psutil.Process(os.getpid())
        metadata['memory_usage'] = process.memory_info().rss / (1024 * 1024)  # In MB
        
        # Get MATLAB version if available
        if self.eng:
            try:
                matlab_version: str = self.eng.eval("version", nargout=1)
                metadata['matlab_version'] = matlab_version
            except:
                pass
                
        return metadata

    def _to_matlab(self, value: Any) -> Any:
        """
        Convert Python values to MATLAB types.
        
        Args:
            value: Python value to convert
            
        Returns:
            MATLAB-compatible value
        """
        if isinstance(value, (list, tuple)):
            if not value:
                return matlab.double([])
            elif isinstance(value[0], (list, tuple)):
                # 2D arrays
                return matlab.double(list(value))
            else:
                # 1D arrays
                return matlab.double([list(value)])
        elif isinstance(value, (int, float)):
            return float(value)
        return value

    def _from_matlab(self, value: Any) -> Any:
        """
        Convert MATLAB types back to Python types.

        Args:
            value: MATLAB value to convert

        Returns:
            Python-compatible value
        """
        if isinstance(value, matlab.double):
            # Get the size of the matlab array
            size = value.size
            if size == (1, 1):
                # Single value
                return float(value[0][0])
            elif size[0] == 1 or size[1] == 1:
                # 1D array (row or column vector)
                return [value[i][0] for i in range(size[0])] if size[0] > 1 else value[0]
            else:
                # 2D array
                return [[value[i][j] for j in range(size[1])] for i in range(size[0])]
        return value


    def close(self) -> None:
        """
        Close the MATLAB engine and release resources.
        """
        if self.eng:
            try:
                self.eng.quit()
                logger.debug("MATLAB engine closed successfully")
            except Exception as e:
                logger.warning(f"Error while closing MATLAB engine: {str(e)}")
                raise  # Rilancia l'eccezione
            finally:
                self.eng = None



def create_response(template_type: str, sim_name: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Create a response based on the template defined in the configuration.
    
    Args:
        template_type: Type of template to use ('success', 'error', 'progress')
        sim_name: Name of the simulation
        **kwargs: Additional fields to include in the response
        
    Returns:
        Formatted response dictionary
    """
    template: Dict[str, Any] = response_templates.get(template_type, {})
    
    # Create base response structure
    response: Dict[str, Any] = {
        'simulation': {
            'name': sim_name,
            'type': 'batch'
        },
        'status': 'completed' if template_type == 'success' else template.get('status', template_type)
    }
    
    # Add timestamp according to configured format
    timestamp_format: str = template.get('timestamp_format', '%Y-%m-%dT%H:%M:%SZ')
    response['timestamp'] = datetime.now().strftime(timestamp_format)
    
    # Add metadata if configured
    if template.get('include_metadata', False) and 'metadata' in kwargs:
        response['metadata'] = kwargs.get('metadata')
    
    # Handle specific template types
    if template_type == 'success':
        response['simulation']['outputs'] = kwargs.get('outputs', {})
    
    elif template_type == 'error':
        error_info: Dict[str, Any] = kwargs.get('error', {})
        response['error'] = {
            'message': error_info.get('message', 'Unknown error'),
            'code': template.get('error_codes', {}).get(
                error_info.get('type', 'execution_error'), 500)
        }
        
        # Add error type if available
        if 'type' in error_info:
            response['error']['type'] = error_info['type']
            
        # Add stack trace if configured
        if template.get('include_stacktrace', False) and 'traceback' in error_info:
            response['error']['traceback'] = error_info['traceback']
    
    elif template_type == 'progress':
        if template.get('include_percentage', False) and 'percentage' in kwargs:
            response['progress'] = {
                'percentage': kwargs['percentage']
            }
    
    # Add any additional keys passed in kwargs
    for key, value in kwargs.items():
        if key not in ['outputs', 'error', 'metadata', 'percentage']:
            response[key] = value
            
    return response


def handle_batch_simulation(parsed_data: Dict[str, Any], source: str, rabbitmq_manager: RabbitMQManager) -> None:
    """
    Process a batch simulation request and send the results back via RabbitMQ.
    
    Args:
        parsed_data: The parsed YAML data containing simulation configuration
        source: Identifier for the simulation request source
        rabbitmq_manager: Instance of RabbitMQManager to send responses
    """
    data: Dict[str, Any] = parsed_data.get('simulation', {})
    sim_name: str = data.get('name', 'Unnamed')
    logger.info(f"Processing batch simulation: {sim_name}")
    
    # Validate input data
    sim_path: Optional[str] = data.get('path')
    sim_file: Optional[str] = data.get('file')
    function_name: Optional[str] = data.get('function_name')
    
    if not sim_path or not sim_file:
        error_response: Dict[str, Any] = create_response(
            'error', 
            sim_name, 
            error={
                'message': "Missing 'path' or 'file' in simulation config.",
                'type': 'invalid_config'
            }
        )
        print(yaml.dump(error_response))
        rabbitmq_manager.send_result(source, error_response)
        return
    
    sim: Optional[MatlabSimulator] = None
    try:
        # Prepare input and output specifications
        inputs: Dict[str, Any] = data.get('inputs', {})
        outputs: List[str] = data.get('outputs', [])
        
        if not outputs:
            raise ValueError("No outputs specified in simulation config")
        
        # Initialize and run the simulation
        sim = MatlabSimulator(sim_path, sim_file, function_name)
        
        # Send progress update if configured
        progress_template: Dict[str, Any] = response_templates.get('progress', {})
        send_progress: bool = progress_template.get('include_percentage', False)
        
        if send_progress:
            progress_response: Dict[str, Any] = create_response(
                'progress', 
                sim_name, 
                percentage=0
            )
            rabbitmq_manager.send_result(source, progress_response)
        
        # Attempt to start MATLAB engine with retry logic
        max_retries: int = 3
        retry_count: int = 0
        while retry_count < max_retries:
            try:
                sim.start()
                break
            except MatlabSimulationError as e:
                retry_count += 1
                if retry_count >= max_retries:
                    raise
                logger.warning(f"MATLAB engine start failed (attempt {retry_count}/{max_retries}). Retrying...")
        
        # Send progress update if configured
        if send_progress:
            progress_response = create_response(
                'progress', 
                sim_name, 
                percentage=50
            )
            rabbitmq_manager.send_result(source, progress_response)
        
        # Run the simulation
        results: Dict[str, Any] = sim.run(inputs, outputs)
        
        # Get metadata if configured
        metadata: Optional[Dict[str, Any]] = None
        if response_templates.get('success', {}).get('include_metadata', False):
            metadata = sim.get_metadata()
        
        # Create success response using the template
        success_response: Dict[str, Any] = create_response(
            'success', 
            sim_name, 
            outputs=results,
            metadata=metadata
        )
        
        print(yaml.dump(success_response))
        
        # Send the result back using the passed instance
        rabbitmq_manager.send_result(source, success_response)
        
        logger.info(f"Simulation '{sim_name}' completed successfully")
        
    except Exception as e:
        logger.error(f"Simulation '{sim_name}' failed: {str(e)}", exc_info=True)
        
        # Determine error type for error code mapping
        error_type: str = 'execution_error'
        if isinstance(e, FileNotFoundError):
            error_type = 'missing_file'
        elif isinstance(e, MatlabSimulationError) and 'MATLAB engine' in str(e):
            error_type = 'matlab_start_failure'
        elif isinstance(e, TimeoutError):
            error_type = 'timeout'
        elif isinstance(e, ValueError):
            error_type = 'invalid_config'
        
        # Create error response using the template
        error_response = create_response(
            'error', 
            sim_name, 
            error={
                'message': str(e),
                'type': error_type,
                'traceback': sys.exc_info() if response_templates.get('error', {}).get('include_stacktrace', False) else None
            }
        )
        
        print(yaml.dump(error_response))
        rabbitmq_manager.send_result(source, error_response)
        
    finally:
        if sim:
            sim.close()