"""
Main entry point for the MATLAB Agent application.
"""
from pathlib import Path
import logging
import click
from base_agent.comm.main_helpers import (
    copy_packaged_resource,
    generate_project_files,
    run_main_with_default_config,
)
from base_agent.utils.logger import setup_logger
from base_agent.utils.config_loader import load_config
from .interfaces.agent import IMatlabAgent
from .core.agent import MatlabAgent

# pylint: disable=import-outside-toplevel,too-many-branches

SIMULATION_WRAPPER_STREAMING = 'SimulationWrapperStreaming.m'
SIMULATION_WRAPPER_INTERACTIVE = 'SimulationWrapperInteractive.m'
SIMULATION_BATCH = 'SimulationBatch.m'
SIMULATION_STREAMING = 'SimulationStreaming.m'
MATLAB_AGENT_RESOURCES = 'matlab_agent.resources'


@click.command()
@click.option('--config-file', '-c', type=click.Path(exists=False),
              default=None, help='Path to custom configuration file')
@click.option('--generate-config', is_flag=True,
              help='Generate a default configuration file in the current directory')
@click.option('--generate-project', is_flag=True,
              help='Generate default project files in the current directory')
def main(config_file=None, generate_config=False,
         generate_project=False) -> None:
    """
    An agent service to manage Matlab simulations.
    """
    run_main_with_default_config(
        config_file=config_file,
        generate_config=generate_config,
        generate_project=generate_project,
        generate_config_func=generate_default_config,
        generate_project_func=generate_default_project,
        run_agent_func=run_agent,
        command_name='matlab-agent',
    )


def generate_default_config():
    """Copy the template configuration file to the current directory if not already present."""
    config_path = Path.cwd() / 'config.yaml'
    if config_path.exists():
        print(f"File already exists at path: {config_path}")
        return
    try:
        copy_packaged_resource(
            package_name='matlab_agent.config',
            resource_name='config.yaml.template',
            output_path=config_path,
        )
        print(f"Configuration template copied to: {config_path}")
    except FileNotFoundError:
        print("Error: Template configuration file not found.")
    except Exception as e:
        print(f"Error generating configuration file: {e}")


def generate_default_project():
    """Copy all template project files to the current directory,
    only if they don't already exist."""

    existing_files = []
    created_files = []

    # Mapping from output filename to importlib resource location
    files_to_generate = {
        'config.yaml': ('matlab_agent.config', 'config.yaml.template'),
        SIMULATION_WRAPPER_STREAMING: (MATLAB_AGENT_RESOURCES,
                                       SIMULATION_WRAPPER_STREAMING),
        SIMULATION_WRAPPER_INTERACTIVE: (MATLAB_AGENT_RESOURCES,
                                         SIMULATION_WRAPPER_INTERACTIVE),
        SIMULATION_BATCH: ('matlab_agent.docs.examples',
                           'simulation_batch.m.template'),
        SIMULATION_STREAMING: ('matlab_agent.docs.examples',
                               'simulation_streaming.m.template'),
        'client/use_matlab_agent_interactive.py': (MATLAB_AGENT_RESOURCES,
                                                   'use_matlab_agent_interactive.py'),
        'client/use_matlab_agent_streaming.py': (MATLAB_AGENT_RESOURCES,
                                                 'use_matlab_agent_streaming.py'),
        'client/use_matlab_agent_batch.py': (MATLAB_AGENT_RESOURCES,
                                             'use_matlab_agent_batch.py'),
        'client/use.yaml': (MATLAB_AGENT_RESOURCES,
                            'use.yaml.template'),
        'client/simulation.yaml': ('matlab_agent.api',
                                   'simulation.yaml.template'),
        'client/README.md': (MATLAB_AGENT_RESOURCES, 'README.md'),
        'client/config/default.yaml': ('matlab_agent.resources.config',
                                       'default.yaml.template'),
    }

    # Descriptions for each file
    file_descriptions = {
        'config.yaml': "Configuration file for the MATLAB agent",
        SIMULATION_WRAPPER_STREAMING: "Helper class for handling streaming simulations",
        SIMULATION_WRAPPER_INTERACTIVE: "Helper class for handling interactive simulations",
        SIMULATION_BATCH: "Template for batch-mode simulations",
        SIMULATION_STREAMING: "Template for streaming-mode simulations",
        'client/use_matlab_agent_interactive.py':
            "Python script to use the MATLAB agent in interactive mode",
        'client/use_matlab_agent_command.py':
            "Python script to send commands to the MATLAB agent",
        'client/use_matlab_agent_streaming.py': "Python script to use the MATLAB agent in streaming mode",
        'client/use_matlab_agent_batch.py': "Python script to use the MATLAB agent in batch mode",
        'client/use.yaml': "Client-side usage configuration (use.yaml)",
        'client/simulation.yaml':
            "Example API payload to communicate with the MATLAB agent",
        'client/README.md': "README file for the client directory",
        'client/config/default.yaml':
            "Default configuration file for the MATLAB agent client (Streaming & Interactive)",
    }

    try:
        # Ensure client directory exists
        Path("client").mkdir(parents=True, exist_ok=True)
        created_files, existing_files = generate_project_files(files_to_generate)

        # Print result summary
        print("\nProject generation summary:\n")

        if created_files:
            print("🆕 Files created:")
            for f in created_files:
                description = file_descriptions.get(
                    f, "No description available")
                print(f" - {f:<35} : {description}")

        if existing_files:
            print("\n📄 Files already present (skipped):")
            for f in existing_files:
                description = file_descriptions.get(
                    f, "No description available")
                print(f" - {f:<35} : {description}")

        if not created_files:
            print("\nAll project files already exist. Nothing was created.")
        else:
            print(
                "\nYou can now customize these files as needed and start using the MATLAB agent.")

    except FileNotFoundError:
        print("❌ Error: One or more template files were not found.")
    except Exception as e:
        print(f"❌ Error generating project files: {e}")


def run_agent(config_file):
    """Initializes and starts a single MATLAB agent instance."""
    broker_type = "rabbitmq"
    config = load_config(package_name="matlab_agent", config_path=config_file)
    logging_level = config['logging']['level']
    logging_file = config['logging']['file']

    logger: logging.Logger = setup_logger(
        name="MATLAB-AGENT",
        level=getattr(logging, logging_level.upper(), logging.INFO),
        log_file=logging_file)

    agent_id = config['agent']['agent_id']
    agent: IMatlabAgent = MatlabAgent(
        agent_id,
        broker_type=broker_type,
        config_path=config_file)

    try:
        logger.debug("Starting MATLAB agent with config: %s", config_file)
        agent.start()
    except KeyboardInterrupt:
        logger.info("Shutting down agent due to keyboard interrupt")
        agent.stop()
    except Exception as e:
        logger.error("Error running agent: %s", e)
        agent.stop()


if __name__ == "__main__":
    main()
