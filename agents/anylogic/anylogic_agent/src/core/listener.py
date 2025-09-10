import socket
import json
import time
import threading
from typing import Any, Dict
from typing import Optional
from ..utils.create_response import create_response
from ..utils.constants import UDP_HOST, UDP_PORT
from ..utils.logger import get_logger
from ..comm.rabbitmq.rabbitmq_manager import RabbitMQManager

logger = get_logger()

class Listener:
    def __init__(self, config: Dict[str, Any], host: str = UDP_HOST, port: int = UDP_PORT) -> None:
        self.host = host
        self.port = port
        self._stop_event = threading.Event()
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self.config = config
        self.response_templates = self.config.get(
            'response_templates', {})
        # Initialize RabbitMQ manager instance for sending results
        agent_id = (self.config.get('agent', {}) or {}).get('agent_id', 'anylogic')
        self.message_broker = RabbitMQManager(agent_id, self.config)
        # Establish connection so we can publish results immediately
        try:
            self.message_broker.connect()
        except Exception:
            # Connection errors will be logged by RabbitMQManager; continue and retry on use
            pass

    def start(self) -> None:
        """Starts UDP listening and prints received messages"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            # Expose socket so stop() can close and unblock recvfrom()
            with self._lock:
                self._sock = sock
            sock.bind((self.host, self.port))
            logger.info(f"UDP - Listening on {self.host}:{self.port}")
            try:
                while not self._stop_event.is_set():
                    try:
                        data, addr = sock.recvfrom(1024)
                    except OSError as e:
                        # Socket closed during shutdown or other error
                        if self._stop_event.is_set():
                            break
                        logger.error(f"Socket error while receiving: {e}")
                        break

                    msg_text = data.decode("utf-8")

                    # HERE we shoud create a response message (RESULT) to send back to the client
                    logger.debug(f"Received from {addr}: {msg_text}")
                    self._process_output(msg_text)

                    try:
                        msg = json.loads(msg_text)
                        send_time = msg.get("simulation_info", {}).get("system_time")
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON")
                        continue

                    if send_time is not None:
                        receive_time = int(time.time() * 1000)
                        delta = receive_time - int(send_time)
                        logger.debug(f"Delay: {delta} ms")
                    else:
                        logger.warning("system_time not found in message")
            except KeyboardInterrupt:
                logger.info("\nStopped by user.")
            finally:
                # Clear reference for safety
                with self._lock:
                    self._sock = None

    def stop(self) -> None:
        """Signal the listener loop to stop."""
        self._stop_event.set()
        # Close the socket to immediately unblock recvfrom()
        with self._lock:
            if self._sock is not None:
                try:
                    self._sock.close()
                except OSError:
                    pass
                
    def _process_output(self, output: Dict[str, Any]) -> None:
        """Process and send individual output chunk."""
        template_type = 'progress' if 'progress' in output else 'streaming'
        data_payload = output if template_type == 'streaming' else output.get('data', {
        })
        # it will be populated with the parameter of the requested simulation
        # response = create_response(
        #     template_type,
        #     self.sim_file,
        #     'streaming',
        #     self.response_templates,
        #     percentage=output.get('progress', {}).get('percentage', sequence),
        #     data=data_payload,
        #     metadata=output.get('metadata', {}),
        #     sequence=sequence,
        #     bridge_meta=self.bridge_meta,
        #     request_id=self.request_id,
        # )
        bridge_meta = {'protocol': 'rabbitmq'}
        request_id = "abcdef12345"
        source = "dt_anylogic"
        response = create_response(
            template_type,
            'simulation.alp',
            'streaming',
            self.response_templates,
            percentage=20,
            data=data_payload,
            metadata=output,
            sequence=1,
            bridge_meta=bridge_meta,
            request_id=request_id,
        )
        # Ensure broker is connected before sending
        if not getattr(self.message_broker, 'channel', None) or not self.message_broker.channel.is_open:
            try:
                self.message_broker.connect()
            except Exception:
                logger.error("Unable to (re)connect to RabbitMQ to send result")
                return
        self.message_broker.send_result(destination=source, result=response)
