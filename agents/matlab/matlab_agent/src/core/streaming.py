"""
streaming.py - MATLAB Simulation Streaming Processor

This module provides functionality to process MATLAB simulation requests requiring
real-time output streaming through the Connect messaging abstraction layer.
"""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import psutil

from ..comm.interfaces import IMessageBroker
from ..utils.create_response import create_response
from ..utils.logger import get_logger

# Configure logger
logger = get_logger()


def handle_streaming_simulation(
    parsed_data: Dict[str, Any],
    source: str,
    message_broker: IMessageBroker,
    path_simulation: str,
    response_templates: Dict,
    tcp_settings: Dict
) -> None:
    """Process streaming simulation request."""
    data = parsed_data.get('simulation', {})
    sim_path = path_simulation if path_simulation else data.get('path')
    sim_file = data.get('file')

    if not sim_path or not sim_file:
        _handle_streaming_error(
            '',
            ValueError("Missing path/file configuration"),
            source,
            message_broker,
            response_templates
        )
        return

    logger.info("Processing streaming simulation: %s", sim_file)
    controller = None

    try:
        controller = MatlabStreamingController(
            sim_path,
            sim_file,
            source,
            message_broker,
            response_templates,
            tcp_settings
        )
        controller.start()
        logger.debug("Simulation inputs: %s", data.get('inputs', {}))
        controller.run(data.get('inputs', {}))
        message_broker.send_result(
            source,
            create_response(
                'success',
                sim_file,
                'streaming',
                response_templates,
                outputs={'status': 'completed'},
                metadata=controller.get_metadata()
            )
        )
        logger.info("Completed: %s", sim_file)

    except Exception as e:  # pylint: disable=broad-except
        logger.error("Simulation failed: %s", str(e))
        _handle_streaming_error(sim_file, e, source, message_broker)
    finally:
        if controller:
            controller.close()


class MatlabStreamingError(Exception):
    """Custom exception for MATLAB streaming errors."""


class StreamingConnection:
    """Manages socket connection and MATLAB process lifecycle."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.connection: Optional[socket.socket] = None
        self.matlab_process: Optional[subprocess.Popen] = None

    def start_server(self) -> None:
        """Start TCP socket server."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen()

    def accept_connection(self, timeout: int = 120) -> None:
        """Accept incoming connection with timeout."""
        self.socket.settimeout(timeout)
        self.connection, _ = self.socket.accept()
        self.connection.settimeout(None)

    def close(self) -> None:
        """Close all connections and processes."""
        if self.connection:
            self.connection.close()
        if self.socket:
            self.socket.close()
        if self.matlab_process and self.matlab_process.poll() is None:
            self.matlab_process.terminate()
            try:
                self.matlab_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.matlab_process.kill()


class MatlabStreamingController:
    """
    Manages the lifecycle of a MATLAB streaming simulation with proper resource management,
    error handling and real-time data transfer.
    """

    def __init__(
        self,
        path: str,
        file: str,
        source: str,
        message_broker: IMessageBroker,
        response_templates: Dict,
        tcp_settings: Dict
    ) -> None:
        self.sim_path: Path = Path(path).resolve()
        self.sim_file: str = file
        self.source: str = source
        self.message_broker: IMessageBroker = message_broker
        self.start_time: Optional[float] = None
        self.response_templates: Dict = response_templates
        host = tcp_settings.get('host', 'localhost')
        port = tcp_settings.get('port', 5678)
        self.connection = StreamingConnection(host, port)
        logger.debug("Path to simulation: %s", self.sim_path)
        logger.debug("Simulation file: %s", self.sim_file)
        # Check if the path is a directory and if the file exists
        # If not, try to find the file in the docs/examples directory
        if not self.sim_path.exists() or not (self.sim_path / self.sim_file).exists():
            logger.error(
                "Directory '%s' or file '%s' not found. Trying fallback in 'docs/examples'.",
                self.sim_path,
                self.sim_file)
            # Define fallback path inside package 'docs/examples'
            fallback_path = (
                Path(__file__).parent.parent.parent /
                "docs" /
                "examples" /
                self.sim_file)
            if fallback_path.exists():
                logger.debug(
                    "Found simulation file in fallback path: '%s'.",
                    fallback_path)
                self.sim_path = fallback_path.parent
            else:
                error_msg = (
                    f"Simulation file '{self.sim_file}' not found in either "
                    f"'{self.sim_path}' or fallback directory '{fallback_path.parent}'.")
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
        self._validate()

    def _validate(self) -> None:
        """Validate simulation path and file."""
        if not self.sim_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {self.sim_path}")
        if not (self.sim_path / self.sim_file).exists():
            raise FileNotFoundError(f"File not found: {self.sim_file}")

    def _start_matlab(self) -> None:
        """Start MATLAB process with subprocess."""
        command = [
            'matlab',
            '-batch',
            f"addpath('{self.sim_path}');"
            f"port = {self.connection.port};"
            f"cd('{self.sim_path}');"
            f"run('{self.sim_file}');"
        ]
        try:
            self.connection.matlab_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        except (subprocess.SubprocessError, Exception) as e:
            logger.error("Failed to start MATLAB process: %s", str(e))
            raise MatlabStreamingError(
                f"Failed to start MATLAB process: {e}") from e

    def start(self) -> None:
        """Start streaming server and MATLAB process."""
        logger.debug("Starting streaming server for: %s", self.sim_file)
        try:
            self.start_time = time.time()
            self.connection.start_server()
            logger.debug(
                "Server started on %s:%d",
                self.connection.host,
                self.connection.port)
            self._start_matlab()
            logger.debug("MATLAB process started")
            self.message_broker.send_result(
                self.source,
                create_response(
                    'progress',
                    self.sim_file,
                    'streaming',
                    self.response_templates,
                    percentage=0,
                    message="MATLAB simulation started"
                )
            )

        except (socket.error, subprocess.SubprocessError) as e:
            logger.error("Startup failed: %s", str(e))
            raise MatlabStreamingError(f"Startup failed: {str(e)}") from e

    def _process_output(self, output: Dict[str, Any], sequence: int) -> None:
        """Process and send individual output chunk."""
        template_type = 'progress' if 'progress' in output else 'streaming'
        data_payload = output if template_type == 'streaming' else output.get('data', {
        })
        response = create_response(
            template_type,
            self.sim_file,
            'streaming',
            self.response_templates,
            percentage=output.get('progress', {}).get('percentage', sequence),
            data=data_payload,
            metadata=output.get('metadata', {}),
            sequence=sequence
        )
        self.message_broker.send_result(self.source, response)

    def run(self, inputs: Dict[str, Any]) -> None:
        """Run simulation and handle streaming data."""
        try:
            logger.debug("Waiting for MATLAB connection...")
            self.connection.accept_connection()
            logger.debug("Sending inputs: %s", inputs)
            self.connection.connection.sendall(
                json.dumps(inputs).encode() + b'\n')

            buffer = b""
            sequence = 0
            while True:
                chunk = self.connection.connection.recv(4096)
                if not chunk:
                    logger.debug("Connection closed")
                    break
                buffer += chunk
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if line.strip():
                        try:
                            logger.debug("Received line: %s", line)
                            self._process_output(
                                json.loads(line.decode()), sequence)
                            sequence += 1
                        except json.JSONDecodeError as e:
                            logger.warning("Invalid JSON: %s", str(e))

        except socket.timeout as e:
            logger.error("Connection timeout: %s", str(e))
            raise MatlabStreamingError("Connection timeout") from e
        except (ConnectionError, OSError) as e:
            logger.error("Connection error: %s", str(e))
            raise MatlabStreamingError(f"Connection error: {str(e)}") from e

    def get_metadata(self) -> Dict[str, Any]:
        """Collect system resource metadata."""
        metadata = {'execution_time': time.time(
        ) - self.start_time} if self.start_time else {}
        process = psutil.Process(os.getpid())
        metadata['memory_usage'] = process.memory_info().rss // (1024 * 1024)

        if self.connection.matlab_process:
            try:
                matlab_proc = psutil.Process(
                    self.connection.matlab_process.pid)
                metadata.update({'matlab_memory': matlab_proc.memory_info(
                ).rss // (1024 * 1024), 'matlab_cpu': matlab_proc.cpu_percent()})
            except psutil.NoSuchProcess:
                pass
        return metadata

    def close(self) -> None:
        """Clean up resources."""
        self.connection.close()


def _handle_streaming_error(
    sim_file: str,
    error: Exception,
    source: str,
    message_broker: IMessageBroker,
    response_templates: Dict
) -> None:
    """Handle error response creation and sending."""
    error_type = 'execution_error'
    if isinstance(error, FileNotFoundError):
        error_type = 'missing_file'
    if isinstance(error, MatlabStreamingError):
        error_type = 'matlab_error'
    if isinstance(
            error,
            ValueError) and "Missing path/file configuration" in str(error):
        error_type = 'bad_request'

    # Log the error type to help debug the issue
    logger.debug("Error Type: %s, Error Message: %s",
                 error_type,
                 str(error))

    message_broker.send_result(
        source,
        create_response(
            'error',
            sim_file,
            'streaming',
            response_templates,
            error={
                'message': str(error),
                'type': error_type,
                'code': 400 if error_type == 'bad_request' else 500,
                'traceback': sys.exc_info() if response_templates.get(
                    'error',
                    {}).get('include_stacktrace') else None}))
