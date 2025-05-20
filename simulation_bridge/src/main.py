"""
Simulation Bridge entry point.
"""
from .core.bridge_orchestrator import BridgeOrchestrator
from .interfaces.bridge_orchestrator import IBridgeOrchestrator
from .utils.logger import setup_logger
from .utils.config_loader import load_config
import click

import logging


@click.command()
@click.option('--config-file', '-c', type=click.Path(exists=True),
              default=None, help='Path to custom configuration file')
def main(config_file=None) -> None:
    """
    Main function to start the Simulation Bridge.
    """
    config = load_config(config_file)
    logging_level = config['logging']['level']
    logging_file = config['logging']['file']
    logger: logging.Logger = setup_logger(
        level=getattr(logging, logging_level.upper(), logging.INFO),
        log_file=logging_file
    )
    simulation_bridge_id = config['simulation_bridge']['simulation_bridge_id']
    bridge: IBridgeOrchestrator = BridgeOrchestrator(
        simulation_bridge_id,
        config_path=config_file)
    try:
        logger.debug("Starting Simulation Bridge with config: %s", config)
        bridge.start()
    except KeyboardInterrupt:
        logger.info("Stopping application via interrupt")
        if bridge:
            bridge.conn.close()
    except Exception as e:
        logger.critical("Critical error: %s", str(e), exc_info=True)
        bridge.stop()


if __name__ == "__main__":
    main()
