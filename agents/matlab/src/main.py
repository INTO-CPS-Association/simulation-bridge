# main.py
"""
Main entry point for the MATLAB Agent application.
"""

import sys
import logging
from .utils.logger import setup_logger
from .core.agent import MatlabAgent

def main():
    """
    Main function to initialize and start the MATLAB agent.
    """
    # Setup logger
    logger = setup_logger(level=logging.DEBUG)

    # Check command line arguments
    if len(sys.argv) != 2:
        logger.error("Usage: main.py <agent_id>")
        sys.exit(1)
    
    # Get agent ID from command line
    agent_id = sys.argv[1]
    
    # Create and start the agent
    agent = MatlabAgent(agent_id)
    try:
        logger.info(f"Starting MATLAB agent with ID: {agent_id}")
        agent.start()
    except KeyboardInterrupt:
        logger.info("Shutting down agent due to keyboard interrupt")
        agent.stop()
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        agent.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()