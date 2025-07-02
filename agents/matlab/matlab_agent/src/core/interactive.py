import json
import os
import socket
import subprocess
import sys
import yaml
import time
import threading
from pathlib import Path
from typing import Any, Dict, Optional
from queue import Queue, Empty

import psutil

from ..comm.interfaces import IMessageBroker
from ..utils.create_response import create_response
from ..utils.logger import get_logger
from ..utils.performance_monitor import PerformanceMonitor

# Configure logger
logger = get_logger()


def handle_interactive_input(ch, method, properties, body, tcp_settings: Dict[str, Any], input_queue: Queue) -> None:
    """Handle incoming interactive input messages and put them in the queue"""
    try:
        msg = yaml.safe_load(body)
        logger.info(f"[INTERACTIVE] Received input frame: {msg}")
        # Put the message in the Queue object
        input_queue.put(msg)
    except Exception as e:
        logger.error(f"[INTERACTIVE] Failed to process input: {e}")


def handle_interactive_simulation(
    msg_dict: Dict[str, Any],
    source: str,
    rabbitmq_manager: IMessageBroker,
    path_simulation: str,
    response_templates: Dict[str, Any],
    tcp_settings: Dict[str, Any]
) -> None:
    """Handle interactive simulation with proper queue management"""
    performance_monitor = PerformanceMonitor()
    operation_id = msg_dict.get('simulation', {}).get('request_id', 'unknown')
    performance_monitor.start_operation(operation_id)

    controller = None

    try:
        data = msg_dict.get('simulation', {})
        request_id = data.get('request_id', '')
        agent_id = data.get('simulator', '')
        bridge_meta = data.get('bridge_meta', 'unknown')
        sim_path = path_simulation if path_simulation else data.get('path')
        sim_file = data.get('file')

        if not sim_path or not sim_file:
            _handle_interactive_error(
                '',
                ValueError("Missing path/file configuration"),
                source,
                rabbitmq_manager,
                response_templates,
                bridge_meta,
                request_id
            )
            return

        logger.info("Processing interactive simulation: %s", sim_file)
        performance_monitor.record_matlab_start()
        controller = MatlabInteractiveController(
            sim_path,
            sim_file,
            source,
            rabbitmq_manager,
            response_templates,
            tcp_settings,
            bridge_meta,
            request_id,
            agent_id = agent_id
        )
        controller.start(performance_monitor)
        controller.run(data.get('inputs', {}), performance_monitor, msg_dict, tcp_settings, request_id)
        performance_monitor.record_matlab_stop()

        success_response = create_response(
            template_type='success',
            sim_file=sim_file,
            sim_type='interactive',
            response_templates=response_templates,
            outputs={'status': 'completed'},
            metadata=controller.get_metadata(),
            bridge_meta=bridge_meta,
            request_id=request_id,
        )
        if rabbitmq_manager.send_result(source, success_response):
            performance_monitor.record_result_sent()
        logger.info("Completed: %s", sim_file)

    except Exception as e:
        logger.error("Error in interactive simulation: %s", e)
        error_response = create_response(
            template_type='error',
            sim_file=sim_file if 'sim_file' in locals() else '',
            sim_type='interactive',
            response_templates=response_templates,
            bridge_meta=bridge_meta if 'bridge_meta' in locals() else 'unknown',
            request_id=request_id if 'request_id' in locals() else 'unknown',
            error={'message': str(e), 'type': 'execution_error'}
        )
        rabbitmq_manager.send_result(source, error_response)
        raise
    finally:
        performance_monitor.complete_operation()
        if controller:
            controller.close()


class MatlabInteractiveError(Exception):
    pass

class InteractiveConnection:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.connection: Optional[socket.socket] = None
        self.matlab_process: Optional[subprocess.Popen] = None

    def start_server(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen()

    def accept_connection(self, timeout: int = 120) -> None:
        self.socket.settimeout(timeout)
        self.connection, _ = self.socket.accept()
        self.connection.settimeout(None)
    
    def send(self, data: dict):
        if self.connection:
            msg = json.dumps(data) + "\n"
            self.connection.sendall(msg.encode())

    def receive(self) -> list:
        buffer = b''
        responses = []
        try:
            chunk = self.connection.recv(4096)
            if chunk:
                buffer += chunk
                lines = buffer.split(b'\n')
                for line in lines[:-1]:
                    if line.strip():
                        responses.append(json.loads(line.decode()))
                buffer = lines[-1]
        except socket.timeout:
            pass
        return responses

    def close(self) -> None:
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


class MatlabInteractiveController:
    def __init__(
        self,
        path: str,
        file: str,
        source: str,
        message_broker: IMessageBroker,
        response_templates: Dict,
        tcp_settings: Dict,
        bridge_meta: Optional[str] = 'unknown',
        request_id: Optional[str] = 'unknown',
        agent_id: Optional[str] = 'agent'
    ) -> None:
        self.sim_path: Path = Path(path).resolve()
        self.agent_id: str = agent_id
        self.sim_file: str = file
        self.bridge_meta: str = bridge_meta
        self.request_id: str = request_id
        self.source: str = source
        self.message_broker: IMessageBroker = message_broker
        self.start_time: Optional[float] = None
        self.response_templates: Dict = response_templates
        host = tcp_settings.get('host', 'localhost')
        port = tcp_settings.get('port', 5678)
        self.connection = InteractiveConnection(host, port)
        self.rabbitmq_manager = message_broker
        if not self.sim_path.exists() or not (self.sim_path / self.sim_file).exists():
            raise FileNotFoundError(f"Simulation file '{self.sim_file}' not found in '{self.sim_path}'")
        self._validate()

    def _validate(self) -> None:
        if not self.sim_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {self.sim_path}")
        if not (self.sim_path / self.sim_file).exists():
            raise FileNotFoundError(f"File not found: {self.sim_file}")

    def _start_matlab(self) -> None:
        command = [
            'matlab',
            '-batch',
            f"addpath('{self.sim_path}');port = {self.connection.port};cd('{self.sim_path}');run('{self.sim_file}');"
        ]
        try:
            self.connection.matlab_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        except Exception as e:
            logger.error("Failed to start MATLAB process: %s", str(e))
            raise MatlabInteractiveError(str(e)) from e

    def start(self, performance_monitor: PerformanceMonitor) -> None:
        try:
            self.start_time = time.time()
            ## here you want to start the TCP server and MATLAB process
            # self.connection.start_server()
            self._start_matlab()
            performance_monitor.record_matlab_startup_complete()
            logger.debug("MATLAB startup duration: %.2fs", time.time() - self.start_time)
            logger.debug("MATLAB process started")
        except Exception as e:
            raise MatlabInteractiveError(str(e)) from e

    def _process_output(self, output: Dict[str, Any], sequence: int) -> None:
        template_type = 'progress' if 'progress' in output else 'interactive'
        data_payload = output if template_type == 'interactive' else output.get('data', {})
        response = create_response(
            template_type,
            self.sim_file,
            'interactive',
            self.response_templates,
            percentage=output.get('progress', {}).get('percentage', sequence),
            data=data_payload,
            metadata=output.get('metadata', {}),
            sequence=sequence,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id,
        )
        self.message_broker.send_result(self.source, response)
        
    def command_producer(input_queue: Queue, delay=0.5):
        directions = ['up', 'right', 'down', 'left']
        i = 0
        while True:
            command = {
                'command': 'move',
                'direction': directions[i % len(directions)]
            }
            input_queue.put(command)
            i += 1
            time.sleep(delay)


    def run(self, inputs: Dict[str, Any], performance_monitor,  msg_dict, tcp_settings, request_id) -> None:
        """Run the interactive simulation with proper Queue handling"""
        tcp = TCPClient()
        tcp.connect()

        input_queue = Queue()
        simulation_data = msg_dict.get('simulation', {})        
        stream_key = simulation_data.get("inputs", {}).get("stream_source", "").replace("rabbitmq://", "")

        # Declare stream exchange and queue binding
        self.rabbitmq_manager.channel.exchange_declare(
            exchange='ex.input.stream',
            exchange_type='topic',
            durable=True
        )

        # Use request_id to create unique queue name
        queue_name = f"Q.{self.agent_id}.interactive.{request_id}"
        result = self.rabbitmq_manager.channel.queue_declare(queue=queue_name, durable=True)
        
        self.rabbitmq_manager.channel.queue_bind(
            exchange='ex.input.stream',
            queue=queue_name,
            routing_key=stream_key
        )

        from functools import partial

        # Pass the actual Queue object, not the string
        callback_with_tcp = partial(handle_interactive_input, tcp_settings=tcp_settings, input_queue=input_queue)

        self.rabbitmq_manager.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback_with_tcp,
            auto_ack=True
        )
        
        # Start the command producer in a separate thread
        threading.Thread(target=self.command_producer, args=(input_queue,), daemon=True).start()

        try:
            logger.debug("Waiting for MATLAB connection...")
            self.connection.accept_connection()
            self.connection.send(inputs)

            while True:
                try:
                    command = input_queue.get(timeout=100)
                    self.connection.send(command)
                    responses = self.connection.receive()
                    for response in responses:
                        self._process_output(response, sequence)
                        sequence += 1
                except socket.error as e:
                    logger.debug("Socket error: %s", e)
                    break
            performance_monitor.record_simulation_complete()

        except socket.timeout as e:
            raise MatlabInteractiveError("Connection timeout") from e
        except (ConnectionError, OSError) as e:
            raise MatlabInteractiveError(f"Connection error: {str(e)}") from e

    def get_metadata(self) -> Dict[str, Any]:
        metadata = {'execution_time': time.time() - self.start_time} if self.start_time else {}
        process = psutil.Process(os.getpid())
        metadata['memory_usage'] = process.memory_info().rss // (1024 * 1024)
        if self.connection.matlab_process:
            try:
                matlab_proc = psutil.Process(self.connection.matlab_process.pid)
                metadata.update({
                    'matlab_memory': matlab_proc.memory_info().rss // (1024 * 1024),
                    'matlab_cpu': matlab_proc.cpu_percent()
                })
            except psutil.NoSuchProcess:
                pass
        return metadata

    def close(self) -> None:
        self.connection.close()


def _handle_interactive_error(
    sim_file: str,
    error: Exception,
    source: str,
    message_broker: IMessageBroker,
    response_templates: Dict,
    bridge_meta: Optional[str] = 'unknown',
    request_id: Optional[str] = 'unknown'
) -> None:
    error_type = 'execution_error'
    if isinstance(error, FileNotFoundError):
        error_type = 'missing_file'
    if isinstance(error, MatlabInteractiveError):
        error_type = 'matlab_error'
    if isinstance(error, ValueError) and "Missing path/file configuration" in str(error):
        error_type = 'bad_request'

    message_broker.send_result(
        source,
        create_response(
            'error',
            sim_file,
            'interactive',
            response_templates,
            bridge_meta=bridge_meta,
            request_id=request_id,
            error={
                'message': str(error),
                'type': error_type,
                'code': 400 if error_type == 'bad_request' else 500,
                'traceback': sys.exc_info() if response_templates.get('error', {}).get('include_stacktrace') else None
            }
        )
    )
