"""
Main entry point for the MATLAB Agent application.
"""
import logging
import click
from .utils.logger import setup_logger
from .interfaces.agent import IMatlabAgent
from .core.agent import MatlabAgent
from .utils.config_loader import load_config


@click.command()
@click.option('--config-file', '-c', type=click.Path(exists=True),
              default=None, help='Path to custom configuration file')
def main(config_file=None) -> None:
    """
    Main function to initialize and start the MATLAB agent.
    Supports single or multiple agents with different configurations.
    """
    run_single_agent(config_file)


def run_single_agent(config_file):
    """ Initializes and starts a single MATLAB agent instance. """
    broker_type = "rabbitmq"
    config = load_config(config_file)
    logging_level = config['logging']['level']
    logging_file = config['logging']['file']
    logger: logging.Logger = setup_logger(
        level=getattr(logging, logging_level.upper(), logging.INFO),
        log_file=logging_file
    )
    agent_id = config['agent']['agent_id']
    agent: IMatlabAgent = MatlabAgent(agent_id, broker_type=broker_type)
    try:
        logger.debug("Starting MATLAB agent with config: %s", config)
        agent.start()
    except KeyboardInterrupt:
        logger.info("Shutting down agent due to keyboard interrupt")
        agent.stop()
    except Exception as e:
        logger.error("Error running agent: %s", e)
        agent.stop()


if __name__ == "__main__":
    main()
