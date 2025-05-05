import asyncio
from typing import Dict, Any, Optional
from ..protocol_adapters.base_adapter import BaseProtocolAdapter
from ..connectors.base_connector import BaseConnector
from ..data_transformation.transformation_manager import DataTransformationManager
from ..data_transformation.json_transformer import JsonToInternalTransformer, InternalToJsonTransformer
from ..models.simulation_state import SimulationState, SimulationStatus
from ..models.command_models import SimulationControlCommand
from ..utils.logger import get_logger
from ..utils.exceptions import BridgeConfigurationError
from datetime import datetime
from ..protocol_adapters.rabbitmq_adapter import RabbitMQAdapter
from ..connectors.matlab_connector import MatlabConnector
import yaml
from pathlib import Path
import logging

logger = get_logger(__name__)

class SimulationBridge:
    def __init__(
        self,
        rabbitmq_adapter: RabbitMQAdapter,
        matlab_connector: MatlabConnector
    ):
        self.adapter = rabbitmq_adapter
        self.connector = matlab_connector
        self.state = SimulationState(
            status=SimulationStatus.STOPPED,
            timestamp=datetime.now()
        )

    async def start(self):
        """Start the bridge"""
        self._update_state(SimulationStatus.STARTING)
        try:
            await self.adapter.connect()
            self._update_state(SimulationStatus.RUNNING)
            await self._message_loop()
        except Exception as e:
            self._update_state(SimulationStatus.ERROR, {'error': str(e)})
            raise

    def _update_state(self, status: SimulationStatus, details: Optional[Dict] = None):
        """Aggiorna lo stato della simulazione"""
        self.state = SimulationState(
            status=status,
            timestamp=datetime.now(),
            details=details
        )
        logger.info(f"State changed to: {status}")

    async def _message_loop(self):
        """Main processing loop"""
        logger.info("Starting message processing loop")
        while self.state.status == SimulationStatus.RUNNING:
            try:
                message = await self.adapter.receive()
                if message:
                    await self._process_message(message)
                
                await asyncio.sleep(0.1)

            except Exception as e:
                self._update_state(SimulationStatus.ERROR, {'error': str(e)})
                logger.error(f"Message loop error: {str(e)}")
                break


    async def _process_message(self, message: Dict[str, Any]):
        """Process a single message"""
        logger.info(f"Processing message: {message}")
        try:
            response = await self.connector.handle_message(message)
            if response['status'] == 'error':
                raise ValueError(response['message'])
                
        except Exception as e:
            logger.error(f"Message processing failed: {str(e)}")
            self._update_state(SimulationStatus.ERROR, {'error': str(e)})
