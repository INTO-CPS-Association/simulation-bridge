from quart import Quart, request, Response
from hypercorn.config import Config as HyperConfig
from hypercorn.asyncio import serve
import asyncio
import yaml
import json
from typing import Dict, Any, Optional, AsyncGenerator
from ...utils.config_manager import ConfigManager
from ...utils.performance_monitor import PerformanceMonitor
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
        """Initialize REST adapter with configuration."""
        super().__init__(config_manager)
        self._active_streams = {}  # Store active streams by client_id
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        self.app = self._create_app()
        logger.debug("REST - Adapter initialized with config: host=%s, port=%s",
                     self.config['host'], self.config['port'])

    def _create_app(self) -> Quart:
        """Factory method to create and configure the Quart app."""
        app = Quart("simulation_rest_adapter")

        @app.post(self.config['endpoint'])
        async def handle_streaming_message() -> Response:
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
                return Response(
                    response=json.dumps(
                        {"error": "Message is not a dictionary"}),
                    status=400,
                    content_type='application/json'
                )

            # Initialize performance monitor
            performance_monitor = PerformanceMonitor()

            simulation = message.get('simulation', {})
            producer = simulation.get('client_id', 'unknown')
            consumer = simulation.get('simulator', 'unknown')
            operation_id = simulation.get('request_id', 'unknown')

            message['bridge_meta'] = {
                'protocol': 'rest',
                'producer': producer,
                'consumer': consumer
            }

            simulation_type = simulation.get('type', 'unknown')
            performance_monitor.start_operation(
                operation_id,
                client_id=producer,
                protocol='rest',
                simulation_type=simulation_type
            )

            signal('message_received_input_rest').send(
                message=message,
                producer=producer,
                consumer=consumer,
                protocol='rest'
            )

            queue = asyncio.Queue()
            self._active_streams[producer] = queue

            return Response(
                self._generate_response(producer, queue),
                content_type='application/x-ndjson',
                status=200
            )

        return app

    def _parse_message(self, body: bytes, content_type: str) -> Dict[str, Any]:
        """Parse message body based on content type."""
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
        self, producer: str, queue: asyncio.Queue
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response."""
        try:
            yield json.dumps({"status": "processing"}) + "\n"
            while True:
                try:
                    result = await asyncio.wait_for(queue.get(), timeout=600)
                    yield json.dumps(result) + "\n"
                    # Check if the status is 'completed' and the execution time is greater than 1 second
                    # This helps prevent issues caused by executions that are
                    # too short or not properly finished
                    if result.get('status') == 'completed' and result.get(
                            'metadata', {}).get('execution_time', 0) > 1:
                        logger.debug(
                            "REST - Final message sent, closing stream")
                        break

                except asyncio.TimeoutError:
                    yield json.dumps({"status": "timeout", "error": "No response received within timeout"}) + "\n"
                    break
                except Exception as e:
                    logger.error("REST - Error in stream: %s", e)
                    yield json.dumps({"status": "error", "error": str(e)}) + "\n"
                    break
        finally:
            self._active_streams.pop(producer, None)

    async def send_result(self, producer: str, result: Dict[str, Any]) -> None:
        """Send a result message to a specific client."""
        if producer in self._active_streams:
            await self._active_streams[producer].put(result)
        else:
            logger.warning(
                "REST - No active stream found for producer: %s",
                producer)

    async def _start_server(self) -> None:
        """Start the Hypercorn server."""
        self._loop = asyncio.get_running_loop()
        config = HyperConfig()
        config.errorlog = logger
        config.accesslog = logger
        config.bind = [f"{self.config['host']}:{self.config['port']}"]
        config.use_reloader = False
        config.worker_class = "asyncio"
        config.alpn_protocols = ["h2", "http/1.1"]

        if self.config['certfile'] and self.config['keyfile']:
            config.certfile = self.config['certfile']
            config.keyfile = self.config['keyfile']

        await serve(self.app, config)

    def start(self) -> None:
        """Start the REST server."""
        logger.debug("REST - Starting adapter on %s:%s",
                     self.config['host'], self.config['port'])
        try:
            asyncio.run(self._start_server())
            self._running = True
        except Exception as e:
            logger.error("REST - Error starting server: %s", e)
            raise

    def send_result_sync(self, producer: str, result: Dict[str, Any]) -> None:
        """Synchronous wrapper for sending result messages."""
        if producer not in self._active_streams:
            logger.warning("REST - No active stream found for producer: %s. Available streams: %s",
                           producer, list(self._active_streams.keys()))
            return

        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self.send_result(producer, result),
                self._loop
            )
            try:
                future.result(timeout=5)
            except Exception as e:
                logger.error("REST - Error sending result: %s", e)
        else:
            logger.error("REST - Event loop not running; cannot send result.")

    def stop(self) -> None:
        """Stop the REST server."""
        logger.debug("REST - Stopping adapter")
        self._running = False

    def _handle_message(self, message: Dict[str, Any]) -> None:
        """(Not used in REST; handled via route)."""
        pass

    def publish_result_message_rest(self, sender, **kwargs):
        """Publish result message via REST adapter."""
        try:
            # Initialize performance monitor
            performance_monitor = PerformanceMonitor()
            message = kwargs.get('message', {})
            operation_id = message.get('request_id', 'unknown')
            destination = message.get('destinations', [])[0]
            self.send_result_sync(destination, message)
            status = message.get('status', 'unknown')
            performance_monitor.record_result_sent(operation_id, 'rest')
            if status == 'completed':
                performance_monitor.finalize_operation(operation_id, 'rest')
            logger.debug(
                "Successfully scheduled result message for REST client: %s",
                destination)
        except (ConnectionError, TimeoutError) as e:
            logger.error("Error sending result message to REST client: %s", e)
