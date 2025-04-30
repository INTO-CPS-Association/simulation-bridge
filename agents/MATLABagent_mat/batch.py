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
from pathlib import Path
from typing import Dict, Union, List, Optional, Any
from datetime import datetime
import matlab.engine
from .rabbitmq.rabbitmq_client import RabbitMQClient
from .utils.logger import get_logger

# Configure logger
logger = get_logger()


class MatlabSimulationError(Exception):
    """Custom exception for MATLAB simulation errors."""
    pass


class MatlabSimulator:
    """
    Manages the lifecycle of a MATLAB simulation with proper resource management,
    error handling and type conversions.
    """
    def __init__(self, path: str, file: str, function_name: Optional[str] = None):
        """
        Initialize a MATLAB simulator.
        
        Args:
            path: Directory path containing the simulation files
            file: Name of the main simulation file
            function_name: Name of the function to call (defaults to file name without extension)
        """
        self.sim_path = Path(path).resolve()
        self.sim_file = file
        self.function_name = function_name or os.path.splitext(file)[0]
        self.eng: Optional[matlab.engine.MatlabEngine] = None
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
            matlab_args = [self._to_matlab(v) for v in inputs.values()]
            
            # Run the MATLAB function
            result = self.eng.feval(self.function_name, *matlab_args, nargout=len(outputs))
            
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
                return value.tolist()[0] if size[0] == 1 else [row[0] for row in value]
            else:
                # 2D array
                return value.tolist()
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
            finally:
                self.eng = None


def handle_batch_simulation(parsed_data: dict, rpc_client: RabbitMQClient, response_queue: str) -> None:
    """
    Process a batch simulation request and send the results back via RabbitMQ.
    
    Args:
        parsed_data: The parsed YAML data containing simulation configuration
        rpc_client: RabbitMQ client to send responses
        response_queue: Queue name to send the response to
    """
    data = parsed_data.get('simulation', {})
    sim_name = data.get('name', 'Unnamed')
    logger.info(f"Processing batch simulation: {sim_name}")
    
    # Prepare the response template
    response_template = {
        'simulation': {
            'name': sim_name,
            'type': 'batch'
        },
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    
    # Validate input data
    sim_path = data.get('path')
    sim_file = data.get('file')
    function_name = data.get('function_name')
    
    if not sim_path or not sim_file:
        error_response = {
            **response_template,
            'status': 'error',
            'error': {
                'message': "Missing 'path' or 'file' in simulation config.",
                'code': 400
            }
        }
        rpc_client.publish(response_queue, yaml.dump(error_response))
        return
    
    sim = None
    try:
        # Prepare input and output specifications
        inputs = data.get('inputs', {})
        outputs = list(data.get('outputs', {}).keys())
        
        if not outputs:
            raise ValueError("No outputs specified in simulation config")
        
        # Initialize and run the simulation
        sim = MatlabSimulator(sim_path, sim_file, function_name)
        
        # Attempt to start MATLAB engine with retry logic
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                sim.start()
                break
            except MatlabSimulationError as e:
                retry_count += 1
                if retry_count >= max_retries:
                    raise
                logger.warning(f"MATLAB engine start failed (attempt {retry_count}/{max_retries}). Retrying...")
        
        # Run the simulation
        results = sim.run(inputs, outputs)
        
        # Prepare success response
        success_response = {
            **response_template,
            'status': 'success',
            'simulation': {
                **response_template['simulation'],
                'outputs': results
            }
        }
        rpc_client.publish(response_queue, yaml.dump(success_response))
        logger.info(f"Simulation '{sim_name}' completed successfully")
        
    except Exception as e:
        # Log the error with traceback
        logger.error(f"Simulation '{sim_name}' failed: {str(e)}", exc_info=True)
        
        # Prepare error response
        error_response = {
            **response_template,
            'status': 'error',
            'error': {
                'message': str(e),
                'code': 500,
                'type': type(e).__name__
            }
        }
        rpc_client.publish(response_queue, yaml.dump(error_response))
        
    finally:
        # Ensure MATLAB engine is always closed
        if sim:
            sim.close()