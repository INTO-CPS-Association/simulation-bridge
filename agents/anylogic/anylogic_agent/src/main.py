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

ANYLOGIC_AGENT_RESOURCES = 'anylogic_agent.resources'
ANYLOGIC_AGENT_API = 'anylogic_agent.api'


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
    An agent service to manage Anylogic simulations.
    """
    if generate_config:
        generate_default_config()
        return
    if generate_project:
        generate_default_project()
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


def generate_default_project():
    """Copy all template project files to the current directory,
    only if they don't already exist."""

    existing_files = []
    created_files = []

    # Mapping from output filename to importlib resource location
    files_to_generate = {
        'config.yaml': ('anylogic_agent.config', 'config.yaml.template'),
        'client/use_anylogic_agent_streaming.py': (ANYLOGIC_AGENT_RESOURCES,
                                                   'use_anylogic_agent_streaming.py'),
        'client/use_anylogic_agent_interactive.py': (ANYLOGIC_AGENT_RESOURCES,
                                                     'use_anylogic_agent_interactive.py'),
        'client/use.yaml': (ANYLOGIC_AGENT_RESOURCES,
                            'use.yaml.template'),
        'client/simulation.yaml': (ANYLOGIC_AGENT_API,
                                   'simulation.yaml.template'),
        'client/README.md': (ANYLOGIC_AGENT_RESOURCES, 'README.md'),
        'template/README.md': (ANYLOGIC_AGENT_RESOURCES, 'TEMPLATE.md'),
        'template/template.alp': (ANYLOGIC_AGENT_RESOURCES, 'template.alp'),
        'template/shared.jar': (ANYLOGIC_AGENT_RESOURCES, 'shared.jar'),
    }

    # Descriptions for each file
    file_descriptions = {
        'config.yaml': "Configuration file for the MATLAB agent",
        'client/use_anylogic_agent_streaming.py': "Example client script for streaming simulations",
        'client/use_anylogic_agent_interactive.py': "Example client script for interactive simulations",
        'client/use.yaml': "YAML configuration for the example client script",
        'client/simulation.yaml': "YAML template for defining simulations",
        'client/README.md': "Instructions for using the example client scripts",
        'template/README.md': "Instructions on how to use the template and start developing your AnyLogic simulation",
        'template/template.alp': "Base AnyLogic project file to start your simulation",
        'template/shared.jar': "Java library required for UDP communication in AnyLogic",
    }

    try:
        # Ensure client directory exists
        Path("client").mkdir(parents=True, exist_ok=True)

        try:
            from importlib.resources import files
            for output_name, (package,
                              resource_name) in files_to_generate.items():
                output_path = Path(output_name)
                if output_path.exists():
                    existing_files.append(output_name)
                    continue
                resource_path = files(package).joinpath(resource_name)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(resource_path, 'rb') as src, open(output_path, 'wb') as dst:
                    dst.write(src.read())
                created_files.append(output_name)
        except (ImportError, AttributeError):
            import pkg_resources
            for output_name, (package,
                              resource_name) in files_to_generate.items():
                output_path = Path(output_name)
                if output_path.exists():
                    existing_files.append(output_name)
                    continue
                template_content = pkg_resources.resource_string(
                    package, resource_name)
                with open(output_path, 'wb') as dst:
                    dst.write(template_content)
                created_files.append(output_name)

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
