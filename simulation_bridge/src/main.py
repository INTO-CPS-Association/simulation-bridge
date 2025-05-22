"""
Simulation Bridge entry point.
"""
import os
from .core.bridge_orchestrator import BridgeOrchestrator
from .interfaces.bridge_orchestrator import IBridgeOrchestrator
from .utils.logger import setup_logger
from .utils.config_loader import load_config
import click

import logging


@click.command()
@click.option('--config-file', '-c', type=click.Path(exists=True),
              default=None, help='Path to custom configuration file')
@click.option('--generate-config', is_flag=True,
              help='Generate a default configuration file in the current directory')
def main(config_file=None, generate_config=False) -> None:
    """
    Main function to start the Simulation Bridge.
    """
    if generate_config:
        generate_default_config()
        return

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

def generate_default_config():
    """Copy the template configuration file to the current directory."""
    try:
        try:
            from importlib.resources import files
            template_path = files('simulation_bridge.config').joinpath(
                'config.yaml.template')
            with open(template_path, 'rb') as src, open('config.yaml', 'wb') as dst:
                dst.write(src.read())
        except (ImportError, AttributeError):
            import pkg_resources
            template_content = pkg_resources.resource_string(
                'simulation_bridge.config', 'config.yaml.template')
            with open('config.yaml', 'wb') as dst:
                dst.write(template_content)
        print(
            f"Configuration template copied to: {os.path.join(os.getcwd(), 'config.yaml')}")
    except FileNotFoundError:
        print("Error: Template configuration file not found.")
    except Exception as e:
        print(f"Error generating configuration file: {e}")


if __name__ == "__main__":
    main()
