"""
Simulation Bridge entry point.
"""
import os
from .core.bridge_orchestrator import BridgeOrchestrator
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
    if config_file:
        run_bridge(config_file)
    else:
        if not os.path.exists('config.yaml'):
            print("""
Error: Configuration file 'config.yaml' not found.

To generate a default configuration file, run:
simulation-bridge --generate-config

You may customize the generated file as needed and re-run the program.

Alternatively, if you already have a custom configuration file, use the
--config-file option to specify its path:
simulation-bridge --config-file /path/to/your/config.yaml
        """)
            return
        else:
            run_bridge('config.yaml')


def run_bridge(config_file):
    """Initializes and starts a single MATLAB agent instance."""
    config = load_config(config_file)
    logging_level = config['logging']['level']
    logging_file = config['logging']['file']

    logger: logging.Logger = setup_logger(
        level=getattr(logging, logging_level.upper(), logging.INFO),
        log_file=logging_file
    )
    simulation_bridge_id = config['simulation_bridge']['bridge_id']
    bridge = BridgeOrchestrator(
        simulation_bridge_id,
        config_path=config_file)
    try:
        logger.debug("Starting Simulation Bridge with config: %s", config)
        bridge.start()
    except KeyboardInterrupt:
        logger.info("Stopping application via interrupt")
        if bridge:
            bridge.stop()
    except Exception as e:
        logger.error("Critical error: %s", str(e), exc_info=True)
        bridge.stop()


def generate_default_config():
    """Copy the template configuration file to the current directory if not already present."""
    config_path = os.path.join(os.getcwd(), 'config.yaml')
    if os.path.exists(config_path):
        print(f"File already exists at path: {config_path}")
        return
    try:
        try:
            from importlib.resources import files
            template_path = files('simulation_bridge.config').joinpath(
                'config.yaml.template')
            with open(template_path, 'rb') as src, open(config_path, 'wb') as dst:
                dst.write(src.read())
        except (ImportError, AttributeError):
            import pkg_resources
            template_content = pkg_resources.resource_string('simulation_bridge.config',
                                                             'config.yaml.template')
            with open(config_path, 'wb') as dst:
                dst.write(template_content)
        print(f"Configuration template copied to: {config_path}")
    except FileNotFoundError:
        print("Error: Template configuration file not found.")
    except Exception as e:
        print(f"Error generating configuration file: {e}")


if __name__ == "__main__":
    main()
