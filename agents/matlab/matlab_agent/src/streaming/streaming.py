"""
streaming.py - MATLAB Simulation Streaming Processor

This module provides functionality to process MATLAB simulation requests requiring
real-time output streaming through RabbitMQ. It handles streaming simulation jobs by:
1. Starting a MATLAB engine via TCP socket connection
2. Running specified simulation files with provided inputs
3. Collecting and streaming simulation outputs in real-time via the message queue
4. Providing proper error handling and logging

Part of the simulation service infrastructure that enables distributed
MATLAB computational workloads with continuous feedback.
"""

import yaml
import os
import time
import sys
import socket
import json
import subprocess
import platform
import psutil
from pathlib import Path
from typing import Dict, Union, List, Optional, Any
from datetime import datetime
import pika
from ..utils.logger import get_logger
from ..utils.config_loader import load_config
from ..core.rabbitmq_manager import RabbitMQManager
from yaml import SafeLoader  # Requires types-PyYAML for type hints

# Configure logger
logger = get_logger()

# Load configuration
config: Dict[str, Any] = load_config()

# Response templates
response_templates: Dict[str, Any] = config.get('response_templates', {})

# TCP settings
tcp_settings: Dict[str, Union[str, int]] = config.get('tcp', {})


class MatlabStreamingError(Exception):
    """Custom exception for MATLAB streaming errors."""
    pass


class MatlabStreamingController:
    """
    Manages the lifecycle of a MATLAB streaming simulation with proper resource management,
    error handling and real-time data transfer.
    """
    def __init__(self, 
                 path: str, 
                 file: str, 
                 source: str, 
                 rabbitmq_manager: RabbitMQManager,
                 ) -> None:
        """
        Initialize a MATLAB streaming controller.
        
        Args:
            path: Directory path containing the simulation files
            file: Name of the main simulation file
            source: Source identifier for RabbitMQ responses
            rabbitmq_manager: RabbitMQ manager instance for sending real-time results
        """
        self.sim_path: Path = Path(path).resolve()
        self.sim_file: str = file
        self.source: str = source
        self.rabbitmq_manager: RabbitMQManager = rabbitmq_manager
        self.matlab_process: Optional[subprocess.Popen] = None
        self.socket: Optional[socket.socket] = None
        self.connection: Optional[socket.socket] = None
        self.host: str = tcp_settings.get('host', 'localhost')
        self.port: int = tcp_settings.get('port', 5678)
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
        Create a socket server and start the MATLAB process.
        
        Raises:
            MatlabStreamingError: If socket creation or MATLAB process fails to start
        """
        logger.debug(f"Starting streaming server for simulation: {self.sim_file}")
        try:
            self.start_time = time.time()
            
            # Create socket server
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen()
            logger.debug(f"Socket server started on {self.host}:{self.port}")
            
            # Start MATLAB process
            command: List[str] = [
                'matlab',
                '-batch',
                f"addpath('{self.sim_path}');"
                f"port = {self.port};"
                f"cd('{self.sim_path}');"
                f"run('{self.sim_file}');"
            ]
            
            self.matlab_process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            
            logger.debug("MATLAB process started successfully")
            
            # Send initial progress message
            progress_template: Dict[str, Any] = response_templates.get('progress', {})
            if progress_template.get('include_percentage', False):
                progress_response: Dict[str, Any] = create_response(
                    'progress', 
                    self.sim_file, 
                    percentage=0,
                    message="MATLAB simulation started"
                )
                self.rabbitmq_manager.send_result(self.source, progress_response)
            
        except socket.error as e:
            logger.error(f"Failed to create socket server: {str(e)}")
            raise MatlabStreamingError(f"Failed to create socket server: {str(e)}") from e
        except Exception as e:
            logger.error(f"Failed to start MATLAB process: {str(e)}")
            raise MatlabStreamingError(f"Failed to start MATLAB process: {str(e)}") from e

    def run(self, inputs: Dict[str, Any]) -> None:
        """
        Accept connection from MATLAB and handle streaming data.
        
        Args:
            inputs: Dictionary of input parameter names to values
            
        Raises:
            MatlabStreamingError: If connection or streaming fails
        """
        if not self.socket:
            raise MatlabStreamingError("Socket server is not started")
            
        try:
            # Set socket timeout for connection waiting
            self.socket.settimeout(120)  # 2 minutes timeout
            logger.debug("Waiting for MATLAB to connect...")
            
            # Accept connection from MATLAB
            self.connection, address = self.socket.accept()
            logger.debug(f"Connected to MATLAB client at {address}")
            
            # Reset timeout for data transmission
            self.connection.settimeout(None)
            
            # Send input data to MATLAB
            logger.debug(f"Sending input data to MATLAB: {inputs}")
            self.connection.sendall(json.dumps(inputs).encode() + b'\n')
            
            # Process incoming data
            buffer: bytes = b""
            sequence: int = 0
            
            while True:
                chunk: bytes = self.connection.recv(4096)
                if not chunk:
                    logger.debug("MATLAB disconnected.")
                    break
                    
                buffer += chunk
                
                # Process complete JSON messages (line-delimited)
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if line.strip():  # Ignore empty lines
                        try:
                            output: Dict[str, Any] = json.loads(line.decode())
                            
                            # Check if this is a progress update or data
                            if 'progress' in output:
                                template_type: str = 'progress'
                                percentage: int = output.get('progress', {}).get('percentage', sequence)
                                metadata: Dict[str, Any] = output.get('metadata', {})
                                
                                streaming_response: Dict[str, Any] = create_response(
                                    template_type,
                                    self.sim_file,
                                    percentage=percentage,
                                    data=output.get('data', {}),
                                    metadata=metadata,
                                    sequence=sequence
                                )
                            else:
                                # Regular data output
                                template_type = 'streaming'
                                streaming_response = create_response(
                                    template_type,
                                    self.sim_file,
                                    data=output,
                                    sequence=sequence
                                )
                                
                            # Send streaming data through RabbitMQ
                            self.rabbitmq_manager.send_result(self.source, streaming_response)
                            sequence += 1
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"Received invalid JSON from MATLAB: {e}")
                
        except socket.timeout:
            logger.error("Timeout waiting for MATLAB connection")
            raise MatlabStreamingError("Timeout waiting for MATLAB connection")
        except ConnectionError as e:
            logger.error(f"Connection error: {str(e)}")
            raise MatlabStreamingError(f"Connection error: {str(e)}") from e
        except Exception as e:
            logger.error(f"Error during streaming: {str(e)}")
            raise MatlabStreamingError(f"Error during streaming: {str(e)}") from e

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the streaming execution.
        
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
        
        # Get MATLAB process info if available
        if self.matlab_process:
            try:
                metadata['matlab_process_running'] = self.matlab_process.poll() is None
                if metadata['matlab_process_running']:
                    matlab_process = psutil.Process(self.matlab_process.pid)
                    metadata['matlab_memory_usage'] = matlab_process.memory_info().rss / (1024 * 1024)  # In MB
                    metadata['matlab_cpu_percent'] = matlab_process.cpu_percent()
            except:
                pass
                
        return metadata

    def close(self) -> None:
        """
        Close the socket connection and terminate the MATLAB process.
        """
        # Close socket connection
        if self.connection:
            try:
                self.connection.close()
                logger.debug("Socket connection closed")
            except Exception as e:
                logger.warning(f"Error while closing socket connection: {str(e)}")
                
        if self.socket:
            try:
                self.socket.close()
                logger.debug("Socket server closed")
            except Exception as e:
                logger.warning(f"Error while closing socket server: {str(e)}")
        
        # Terminate MATLAB process
        if self.matlab_process and self.matlab_process.poll() is None:
            try:
                logger.debug("Terminating MATLAB process...")
                self.matlab_process.terminate()
                try:
                    self.matlab_process.wait(timeout=10)
                    logger.debug("MATLAB process terminated successfully")
                except subprocess.TimeoutExpired:
                    self.matlab_process.kill()  # Force kill if not terminated
                    logger.debug("MATLAB process was forcefully killed")
            except Exception as e:
                logger.warning(f"Error while terminating MATLAB process: {str(e)}")


def create_response(template_type: str, sim_file: str, **kwargs) -> Dict[str, Any]:
    """
    Create a response based on the template defined in the configuration.
    
    Args:
        template_type: Type of template to use ('success', 'error', 'progress', 'streaming')
        sim_file: Name of the simulation
        **kwargs: Additional fields to include in the response
        
    Returns:
        Formatted response dictionary
    """
    template: Dict[str, Any] = response_templates.get(template_type, {})
    
    # Create base response structure
    response: Dict[str, Any] = {
        'simulation': {
            'file': sim_file,
            'type': 'streaming'
        },
        'status': template.get('status', template_type)
    }
    
    # Add timestamp according to configured format
    timestamp_format: str = template.get('timestamp_format', '%Y-%m-%dT%H:%M:%SZ')
    response['timestamp'] = datetime.now().strftime(timestamp_format)
    
    # Add sequence number if available
    if 'sequence' in kwargs:
        response['sequence'] = kwargs['sequence']
    
    # Add metadata if configured
    if template.get('include_metadata', False) and 'metadata' in kwargs:
        response['metadata'] = kwargs.get('metadata')
    
    # Handle specific template types
    if template_type == 'success':
        response['simulation']['outputs'] = kwargs.get('data', {})
    
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
            
        # Add streaming data if available
        if 'data' in kwargs and kwargs['data']:
            response['data'] = kwargs['data']
    
    elif template_type == 'streaming':
        # Add streaming data
        if 'data' in kwargs:
            response['data'] = kwargs['data']
    
    # Add any additional keys passed in kwargs
    for key, value in kwargs.items():
        if key not in ['data', 'error', 'metadata', 'percentage', 'sequence']:
            response[key] = value
            
    return response


def handle_streaming_simulation(parsed_data: Dict[str, Any], source: str, rabbitmq_manager: RabbitMQManager) -> None:
    """
    Process a streaming simulation request and send the results back via RabbitMQ in real-time.
    
    Args:
        parsed_data: The parsed YAML data containing simulation configuration
        source: Identifier for the simulation request source
        rabbitmq_manager: Instance of RabbitMQManager to send streaming responses
    """
    data: Dict[str, Any] = parsed_data.get('simulation', {})
        
    # Validate input data
    sim_path= config['simulation']['path'] # Default path from config
    sim_file: Optional[str] = data.get('file')
    logger.info(f"Processing streaming simulation: {sim_file}")
    
    if not sim_path or not sim_file:
        error_response: Dict[str, Any] = create_response(
            'error', 
            sim_file, 
            error={
                'message': "Missing 'path' or 'file' in simulation config.",
                'type': 'invalid_config'
            }
        )
        print(yaml.dump(error_response))
        rabbitmq_manager.send_result(source, error_response)
        return
    
    controller: Optional[MatlabStreamingController] = None
    try:
        # Prepare input specifications
        inputs: Dict[str, Any] = data.get('inputs', {})
        
        # Initialize the streaming controller
        controller = MatlabStreamingController(
            sim_path, 
            sim_file, 
            source, 
            rabbitmq_manager
        )
        
        # Start the streaming server and MATLAB process
        controller.start()
        
        # Run the simulation - this will handle the streaming connections
        controller.run(inputs)
        
        # Get metadata for final response
        metadata: Dict[str, Any] = controller.get_metadata()
        
        # Send final success message indicating completion
        success_response: Dict[str, Any] = create_response(
            'success', 
            sim_file, 
            data={'status': 'completed'},
            metadata=metadata
        )
        
        print(yaml.dump(success_response))
        rabbitmq_manager.send_result(source, success_response)
        
        logger.info(f"Streaming simulation '{sim_file}' completed successfully")
        
    except Exception as e:
        logger.error(f"Streaming simulation '{sim_file}' failed: {str(e)}", exc_info=True)
        
        # Determine error type for error code mapping
        error_type: str = 'execution_error'
        if isinstance(e, FileNotFoundError):
            error_type = 'missing_file'
        elif isinstance(e, MatlabStreamingError) and 'socket server' in str(e):
            error_type = 'socket_creation_failure'
        elif isinstance(e, MatlabStreamingError) and 'MATLAB process' in str(e):
            error_type = 'matlab_start_failure'
        elif isinstance(e, TimeoutError) or (isinstance(e, MatlabStreamingError) and 'Timeout' in str(e)):
            error_type = 'timeout'
        elif isinstance(e, ValueError):
            error_type = 'invalid_config'
        
        # Create error response using the template
        error_response: Dict[str, Any] = create_response(
            'error', 
            sim_file, 
            error={
                'message': str(e),
                'type': error_type,
                'traceback': sys.exc_info() if response_templates.get('error', {}).get('include_stacktrace', False) else None
            }
        )
        
        print(yaml.dump(error_response))
        rabbitmq_manager.send_result(source, error_response)
        
    finally:
        # Ensure proper cleanup
        if controller:
            controller.close()