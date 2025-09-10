"""
Main entry point for the ANYLOGIC Agent application.
"""
from pathlib import Path
import logging
import click
from .utils.logger import setup_logger
from .interfaces.agent import IAnylogicAgent
from .core.agent import AnylogicAgent
from .utils.config_loader import load_config

# pylint: disable=import-outside-toplevel,too-many-branches

@click.command()
@click.option('--config-file', '-c', type=click.Path(exists=False),
              default=None, help='Path to custom configuration file')
@click.option('--generate-config', is_flag=True,
              help='Generate a default configuration file in the current directory')
def main(config_file=None, generate_config=False) -> None:
    """
    An agent service to manage Anylogic simulations.
    """
    if generate_config:
        generate_default_config()
        return
    if config_file:
        run_agent(config_file)
    else:
        config_path = Path('config.yaml')
        if not config_path.exists():
            print("""
Error: Configuration file 'config.yaml' not found.

To generate a default configuration file, run:
anylogic-agent --generate-config

You may customize the generated file as needed and re-run the program.

Alternatively, if you already have a custom configuration file, use the
--config-file option to specify its path:
anylogic-agent --config-file /path/to/your/config.yaml
        """)
            return
        else:
            run_agent(str(config_path))


def generate_default_config():
    """Copy the template configuration file to the current directory if not already present."""
    config_path = Path.cwd() / 'config.yaml'
    if config_path.exists():
        print(f"File already exists at path: {config_path}")
        return
    try:
        try:
            from importlib.resources import files
            template_path = files('anylogic_agent.config').joinpath(
                'config.yaml.template')
            with open(template_path, 'rb') as src, open(config_path, 'wb') as dst:
                dst.write(src.read())
        except (ImportError, AttributeError):
            import pkg_resources
            template_content = pkg_resources.resource_string('anylogic_agent.config',
                                                             'config.yaml.template')
            with open(config_path, 'wb') as dst:
                dst.write(template_content)
        print(f"Configuration template copied to: {config_path}")
    except FileNotFoundError:
        print("Error: Template configuration file not found.")
    except Exception as e:
        print(f"Error generating configuration file: {e}")

def run_agent(config_file):
    """Initializes and starts a single ANYLOGIC Agent instance."""
    broker_type = "rabbitmq"
    config = load_config(config_file)
    logging_level = config['logging']['level']
    logging_file = config['logging']['file']

    logger: logging.Logger = setup_logger(
        level=getattr(logging, logging_level.upper(), logging.INFO),
        log_file=logging_file)

    agent_id = config['agent']['agent_id']
    agent: IAnylogicAgent = AnylogicAgent(
        agent_id,
        broker_type=broker_type,
        config_path=config_file)

    try:
        logger.debug("Starting ANYLOGIC Agent with config: %s", config_file)
        agent.start()
    except KeyboardInterrupt:
        logger.info("Shutting down agent due to keyboard interrupt")
        agent.stop()
    except Exception as e:
        logger.error("Error running agent: %s", e)
        agent.stop()


if __name__ == "__main__":
    main()
