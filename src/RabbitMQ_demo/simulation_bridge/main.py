# main.py
from simulation_bridge import SimulationBridge
from utils.logger import setup_logger
import logging

if __name__ == "__main__":
    logger = setup_logger(level=logging.INFO)
    try:
        logger.info("Started Simulation Bridge")
        bridge = SimulationBridge()
        bridge.start()
    except KeyboardInterrupt:
        logger.info("Stopping application via interrupt")
        bridge.conn.close()
    except Exception as e:
        logger.critical(f"Critical error: {str(e)}", exc_info=True)
        raise