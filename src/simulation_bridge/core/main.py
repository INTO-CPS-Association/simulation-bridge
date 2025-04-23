import asyncio
import pika
import yaml
from pathlib import Path

from ..utils.logger import setup_logging, get_logger
from ..protocol_adapters.rabbitmq_adapter import RabbitMQAdapter
from ..connectors.matlab_connector import MatlabConnector
from .simulation_bridge_core import SimulationBridge

# Setup global logging
setup_logging()
logger = get_logger(__name__)

def load_config() -> dict:
    config_path = Path(__file__).parent / "config" / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    rabbitmq_cfg = config["rabbitmq"]

    rabbitmq_config = {
        'port': rabbitmq_cfg["port"],
        'host': rabbitmq_cfg["host"],
        'credentials': pika.PlainCredentials(
            rabbitmq_cfg["username"], rabbitmq_cfg["password"]
        ),
        'exchange': rabbitmq_cfg["exchange"],
        'exchange_type': rabbitmq_cfg["exchange_type"],
        'routing_key': rabbitmq_cfg["routing_key"]
    }

    adapter = RabbitMQAdapter(rabbitmq_config)
    connector = MatlabConnector(adapter)
    bridge = SimulationBridge(adapter, connector)

    try:
        logger.info("Avvio del Simulation Bridge...")
        asyncio.run(bridge.start())
    except KeyboardInterrupt:
        logger.info("Bridge interrotto dall'utente")
    except Exception as e:
        logger.error(f"Errore fatale: {str(e)}")

if __name__ == "__main__":
    main()
