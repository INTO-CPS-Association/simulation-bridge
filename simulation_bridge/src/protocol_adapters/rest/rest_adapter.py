from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from blinker import signal
import yaml
import json
from ...utils.config_manager import ConfigManager
from ...utils.logger import get_logger
import uvicorn
from typing import Dict, Any
from ..base.protocol_adapter import ProtocolAdapter

logger = get_logger()

class RESTAdapter(ProtocolAdapter):
    def _get_config(self) -> Dict[str, Any]:
        return self.config_manager.get_rest_config()
        
    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        self.app = FastAPI(title="Simulation Bridge REST API")
        self._setup_routes()
        logger.debug(f"REST - Adapter initialized with config: host={self.config['host']}, port={self.config['port']}")

    def _setup_routes(self):
        """Setup all REST endpoints"""
        self.app.post(self.config['input_endpoint'])(self._handle_input_message)

    async def _handle_input_message(self, request: Request) -> JSONResponse:
        """Handle incoming messages on the input endpoint"""
        content_type = request.headers.get('content-type', '')
        body = await request.body()
        
        try:
            if 'yaml' in content_type:
                logger.debug("REST - Attempting to parse message as YAML")
                message = yaml.safe_load(body)
            elif 'json' in content_type:
                logger.debug("REST - Attempting to parse message as JSON")
                message = json.loads(body)
            else:
                # fallback: try YAML, then JSON, then raw text
                try:
                    logger.debug("REST - Attempting to parse message as YAML (fallback)")
                    message = yaml.safe_load(body)
                except Exception:
                    try:
                        logger.debug("REST - Attempting to parse message as JSON (fallback)")
                        message = json.loads(body)
                    except Exception:
                        logger.debug("REST - Parsing as raw text (fallback)")
                        message = {
                            "content": body.decode('utf-8', errors='replace'),
                            "raw_message": True
                        }
        except Exception as e:
            logger.error(f"REST - Error parsing message: {e}")
            raise HTTPException(status_code=400, detail=str(e))

        if not isinstance(message, dict):
            logger.error("REST - Message is not a dictionary")
            raise HTTPException(status_code=400, detail="Message is not a dictionary")

        simulation = message.get('simulation', {})
        producer = simulation.get('client_id', 'unknown')
        consumer = simulation.get('simulator', 'unknown')

        # Add bridge metadata
        message['bridge_meta'] = {
            'protocol': 'rest',
            'producer': producer,
            'consumer': consumer
        }

        logger.debug(f"REST - Processing message from producer: {producer}, simulator: {consumer}")
        signal('message_received_input_rest').send(
            message=message,
            producer=producer,
            consumer=consumer
        )
        return JSONResponse(content={"status": "received"})

    def start(self):
        """Start the REST server"""
        logger.debug(f"REST - Starting adapter on {self.config['host']}:{self.config['port']}")
        try:
            uvicorn.run(
                self.app,
                host=self.config['host'],
                port=self.config['port'],
                log_level="error"  # Disable uvicorn logs since we use our own logging
            )
        except Exception as e:
            logger.error(f"REST - Error starting server: {e}")
            raise

    def stop(self):
        """Stop the REST server"""
        logger.info("REST - Stopping adapter")
        # FastAPI/uvicorn doesn't have a direct stop method, but we can implement
        # a shutdown mechanism if needed in the future
        pass
        
    def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming messages (required by ProtocolAdapter)"""
        # For REST, this is handled by the FastAPI endpoint
        pass 