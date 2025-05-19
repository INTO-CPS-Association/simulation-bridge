# main.py
from .simulation_bridge import SimulationBridge
from .utils.logger import setup_logger
import logging
from typing import Optional
import os
from pathlib import Path

os.chdir(Path(__file__).parent)


def main() -> None:
    logger: logging.Logger = setup_logger(level=logging.INFO)
    bridge: Optional[SimulationBridge] = None
    try:
        logger.info("Starting Simulation Bridge...")
        bridge = SimulationBridge()
        bridge.start()
    except KeyboardInterrupt:
        logger.info("Stopping application via interrupt")
        if bridge:
            bridge.conn.close()
    except Exception as e:
        logger.critical(f"Critical error: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
