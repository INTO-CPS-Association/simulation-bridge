"""
Main entry point for the MATLAB Agent application.
"""
import logging
import click
from .utils.logger import setup_logger
from .core.agent import MatlabAgent
from .utils.config_loader import load_config

@click.command()
@click.argument('agent_id', required=False)
def main(agent_id=None) -> None:
    """
    Main function to initialize and start the MATLAB agent.
    
    Args:
        agent_id: The ID of the agent to start. If not provided, will use default from config.
    """
    config = load_config()
    logging_level = config['logging']['level']
    logging_file = config['logging']['file']
    
    # Setup logger
    logger: logging.Logger = setup_logger(
        level=getattr(logging, logging_level.upper(), logging.INFO), #in case of invalid level, default to INFO
        log_file=logging_file)
    
    # Use default agent_id from config if not provided
    if agent_id is None:
        agent_id = config['agent']['agent_id']
        logger.debug(f"Using default agent_id: {agent_id}")
    
    # Create and start the agent
    agent: MatlabAgent = MatlabAgent(agent_id)
    try:
        logger.debug(f"Starting MATLAB agent..")
        agent.start()
    except KeyboardInterrupt:
        logger.info("Shutting down agent due to keyboard interrupt")
        agent.stop()
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        agent.stop()

if __name__ == "__main__":
    main()