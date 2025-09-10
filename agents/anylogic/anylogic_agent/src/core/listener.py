import socket
import json
import time
import threading
from typing import Optional
from ..utils.constants import UDP_HOST, UDP_PORT
from ..utils.logger import get_logger

logger = get_logger()

class Listener:
    def __init__(self, host: str = UDP_HOST, port: int = UDP_PORT) -> None:
        self.host = host
        self.port = port
        self._stop_event = threading.Event()
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Starts UDP listening and prints received messages"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            # Expose socket so stop() can close and unblock recvfrom()
            with self._lock:
                self._sock = sock
            sock.bind((self.host, self.port))
            logger.info(f"Listening on {self.host}:{self.port}")
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

                    try:
                        msg = json.loads(msg_text)
                        send_time = msg.get("simulation_info", {}).get("system_time")
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON")
                        continue

                    if send_time is not None:
                        receive_time = int(time.time() * 1000)
                        delta = receive_time - int(send_time)
                        logger.info(f"Delay: {delta} ms")
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
