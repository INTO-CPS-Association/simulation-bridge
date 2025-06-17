"""
Simulation Bridge entry point.
"""
import logging
import os

import click

from .core.bridge_orchestrator import BridgeOrchestrator
from .utils.config_loader import load_config
from .utils.logger import setup_logger
from .utils.template import generate_default_config, generate_default_project

CONFIG_FILENAME = 'config.yaml'


@click.command()
@click.option('--config-file', '-c', type=click.Path(exists=True),
              default=None, help='Path to custom configuration file')
@click.option('--generate-config', is_flag=True,
              help='Generate a default configuration file in the current directory')
@click.option('--generate-project', is_flag=True,
              help='Generate default project files in the current directory')
def main(
        config_file=None,
        generate_config=False,
        generate_project=False) -> None:
    """
    Main function to start the Simulation Bridge.
    """
    if generate_config:
        generate_default_config()
        return

    if generate_project:
        generate_default_project()
        return

    if config_file:
        run_bridge(config_file)
        return

    if not os.path.exists(CONFIG_FILENAME):
        print(f"""
Error: Configuration file {CONFIG_FILENAME} not found.

To generate a default configuration file, run:
simulation-bridge --generate-config

You may customize the generated file as needed and re-run the program.

Alternatively, if you already have a custom configuration file, use the
--config-file option to specify its path:
simulation-bridge --config-file /path/to/your/config.yaml
        """)
        return

    run_bridge(CONFIG_FILENAME)


def run_bridge(config_file):
    """Initializes and starts a single MATLAB agent instance."""
    config = load_config(config_file)
    logging_level = config['logging']['level']
    logging_file = config['logging']['file']

    logger: logging.Logger = setup_logger(
        level=getattr(logging, logging_level.upper(), logging.INFO),
        log_file=logging_file
    )
    bridge = BridgeOrchestrator(config_path=config_file)
    try:
        logger.debug("Starting Simulation Bridge with config: %s", config)
        bridge.start()
    except KeyboardInterrupt:
        logger.info("Stopping application via interrupt")
        if bridge:
            bridge.stop()
    except OSError as e:
        logger.error("OS error: %s", str(e), exc_info=True)
        bridge.stop()
    except ValueError as e:
        logger.error("Configuration error: %s", str(e), exc_info=True)
        bridge.stop()


if __name__ == "__main__":
    main()
