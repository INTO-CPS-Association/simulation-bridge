from typing import Dict, Any
from .base_connector import BaseConnector
from ..utils.logger import get_logger
from ..models.command_models import SimulationControlCommand
from ..protocol_adapters.rabbitmq_adapter import RabbitMQAdapter
from datetime import datetime

logger = get_logger(__name__)

class MatlabConnector:
    def __init__(self, adapter: RabbitMQAdapter):
        self.adapter = adapter
        self.simulation_data = None

    async def handle_message(self, message: Dict[str, Any]):
        """Process simulation data and send via RabbitMQ"""
        try:
            self.simulation_data = message.get('simulation')
            
            if not self.simulation_data:
                raise ValueError("Missing simulation data in message")
            
            # Invia i dati della simulazione via RabbitMQ
            await self.adapter.send({
                'simulation': self.simulation_data,
                'timestamp': datetime.now().isoformat()
            })
            
            return {'status': 'success', 'message': 'Data processed'}
            
        except Exception as e:
            logger.error(f"MATLAB processing failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}
