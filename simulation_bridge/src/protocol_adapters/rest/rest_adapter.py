from quart import Quart, request, Response
from hypercorn.config import Config as HyperConfig
from hypercorn.asyncio import serve
import asyncio
import yaml
import json
from typing import Dict, Any, Optional, AsyncGenerator
from ...utils.config_manager import ConfigManager
from ...utils.logger import get_logger
from ..base.protocol_adapter import ProtocolAdapter
from blinker import signal

logger = get_logger()


class RESTAdapter(ProtocolAdapter):
    """REST protocol adapter implementation using Quart and Hypercorn."""

    def _get_config(self) -> Dict[str, Any]:
        """Get REST configuration from config manager."""
        return self.config_manager.get_rest_config()

    def __init__(self, config_manager: ConfigManager):
        """Initialize REST adapter with configuration.

        Args:
            config_manager: Configuration manager instance
        """
        super().__init__(config_manager)
        self.app = Quart(__name__)
        self._setup_routes()
        self.server = None
        self._active_streams = {}  # Store active streams by client_id
        # Main event loop
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False

        logger.debug("REST - Adapter initialized with config: host=%s, port=%s",
                     self.config['host'], self.config['port'])

    def _setup_routes(self) -> None:
        """Set up the streaming endpoint."""
        self.app.post(self.config['endpoint'])(self._handle_streaming_message)

    async def _handle_streaming_message(self) -> Response:
        """Handle incoming messages with streaming response.

        Returns:
            Response: Streaming response with simulation results
        """
        content_type = request.headers.get('content-type', '')
        body = await request.get_data()

        try:
            message = self._parse_message(body, content_type)
        except Exception as e:
            logger.error("REST - Error parsing message: %s", e)
            return Response(
                response=json.dumps({"error": str(e)}),
                status=400,
                content_type='application/json'
            )

        if not isinstance(message, dict):
            logger.error("REST - Message is not a dictionary")
            return Response(
                response=json.dumps({"error": "Message is not a dictionary"}),
                status=400,
                content_type='application/json'
            )

        simulation = message.get('simulation', {})
        producer = simulation.get('client_id', 'unknown')
        consumer = simulation.get('simulator', 'unknown')

        # Add bridge metadata
        message['bridge_meta'] = {
            'protocol': 'rest',
            'producer': producer,
            'consumer': consumer
        }

        logger.debug(
            "REST - Processing message from producer: %s, simulator: %s",
            producer, consumer)
        signal('message_received_input_rest').send(
            message=message,
            producer=producer,
            consumer=consumer
        )

        # Create a queue for this client's messages
        queue = asyncio.Queue()
        self._active_streams[producer] = queue

        return Response(
            self._generate_response(producer, queue),
            content_type='application/x-ndjson',
            status=200
        )

    def _parse_message(self, body: bytes, content_type: str) -> Dict[str, Any]:
        """Parse message body based on content type.

        Args:
            body: Raw message body
            content_type: Content type header

        Returns:
            Dict[str, Any]: Parsed message
        """
        if 'yaml' in content_type:
            logger.debug("REST - Attempting to parse message as YAML")
            return yaml.safe_load(body)
        elif 'json' in content_type:
            logger.debug("REST - Attempting to parse message as JSON")
            return json.loads(body)

        # Fallback: try YAML, then JSON, then raw text
        try:
            logger.debug(
                "REST - Attempting to parse message as YAML (fallback)")
            return yaml.safe_load(body)
        except Exception:
            try:
                logger.debug(
                    "REST - Attempting to parse message as JSON (fallback)")
                return json.loads(body)
            except Exception:
                logger.debug("REST - Parsing as raw text (fallback)")
                return {
                    "content": body.decode('utf-8', errors='replace'),
                    "raw_message": True
                }

    async def _generate_response(
        self, producer: str, queue: asyncio.Queue) -> AsyncGenerator[str, None]:
        """Generate streaming response.

        Args:
            producer: Client ID
            queue: Message queue for this client

        Yields:
            str: JSON-encoded messages
        """
        try:
            # Send initial acknowledgment
            yield json.dumps({"status": "processing"}) + "\n"
            # Keep the connection open and wait for results
            while True:
                try:
                    result = await asyncio.wait_for(queue.get(), timeout=600)
                    yield json.dumps(result) + "\n"
                except asyncio.TimeoutError:
                    yield json.dumps({"status": "timeout", "error": "No response received within timeout"}) + "\n"
                    break
                except Exception as e:
                    logger.error("REST - Error in stream: %s", e)
                    yield json.dumps({"status": "error", "error": str(e)}) + "\n"
                    break
        finally:
            # Clean up when the stream ends
            if producer in self._active_streams:
                del self._active_streams[producer]

    async def send_result(self, producer: str, result: Dict[str, Any]) -> None:
        """Send a result message to a specific client.

        Args:
            producer: Client ID
            result: Result message to send
        """
        if producer in self._active_streams:
            await self._active_streams[producer].put(result)
        else:
            logger.warning(
                "REST - No active stream found for producer: %s", producer)

    async def _start_server(self) -> None:
        """Start the Hypercorn server."""
        self._loop = asyncio.get_running_loop()  # Save main event loop

        config = HyperConfig()
        config.errorlog = logger  # Use the main logger for error logs
        config.accesslog = logger  # Use the main logger for access logs
        config.bind = ["%s:%s" % (self.config['host'], self.config['port'])]
        config.use_reloader = False
        config.worker_class = "asyncio"
        config.alpn_protocols = ["h2", "http/1.1"]

        if self.config.get('certfile') and self.config.get('keyfile'):
            config.certfile = self.config['certfile']
            config.keyfile = self.config['keyfile']
        await serve(self.app, config)

    def start(self) -> None:
        """Start the REST server."""
        logger.debug(
            "REST - Starting adapter on %s:%s",
            self.config['host'], self.config['port'])
        try:
            asyncio.run(self._start_server())
            self._running = True
        except Exception as e:
            logger.error("REST - Error starting server: %s", e)
            raise

    def send_result_sync(self, producer: str, result: Dict[str, Any]) -> None:
        """Synchronous wrapper for sending result messages.

        Args:
            producer: Client ID
            result: Result message to send
        """
        if producer not in self._active_streams:
            logger.warning(
                "REST - No active stream found for producer: %s. "
                "Available streams: %s",
                producer, list(self._active_streams.keys())
            )
            return

        if self._loop and self._loop.is_running():
            # Use run_coroutine_threadsafe to execute coroutine in main loop
            future = asyncio.run_coroutine_threadsafe(
                self.send_result(producer, result),
                self._loop
            )
            try:
                # Optional: wait for result with short timeout
                future.result(timeout=5)
            except Exception as e:
                logger.error("REST - Error sending result: %s", e)
        else:
            logger.error("REST - Event loop not running; cannot send result.")

    def stop(self) -> None:
        """Stop the REST server."""
        logger.debug("REST - Stopping adapter")
        self._running = False
        if self.server:
            self.server.close()

    def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming messages (required by ProtocolAdapter).

        Args:
            message: Message to handle
        """
        # For REST, this is handled by the Quart endpoint
        pass
