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
ANYLOGIC_CONFIG_FILE_TEMPLATE = 'config.yaml.template'
ANYLOGIC_AGENT_CONFIG = 'anylogic_agent.config'
ANYLOGIC_AGENT_API = 'anylogic_agent.api'
ANYLOGIC_CONFIG_FILE = 'config.yaml'


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
        config_path = Path(ANYLOGIC_CONFIG_FILE)
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
        else:
            run_agent(str(config_path))


def generate_default_config():
    """Copy the template configuration file to the current directory if not already present."""
    config_path = Path.cwd() / ANYLOGIC_CONFIG_FILE
    if config_path.exists():
        print(f"File already exists at path: {config_path}")
        return
    try:
        try:
            from importlib.resources import files
            template_path = files(ANYLOGIC_AGENT_CONFIG).joinpath(
                ANYLOGIC_CONFIG_FILE_TEMPLATE)
            with open(template_path, 'rb') as src, open(config_path, 'wb') as dst:
                dst.write(src.read())
        except (ImportError, AttributeError):
            import pkg_resources
            template_content = pkg_resources.resource_string(ANYLOGIC_AGENT_CONFIG,
                                                             ANYLOGIC_CONFIG_FILE_TEMPLATE)
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
        ANYLOGIC_CONFIG_FILE: (ANYLOGIC_AGENT_CONFIG, ANYLOGIC_CONFIG_FILE_TEMPLATE),
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
        ANYLOGIC_CONFIG_FILE: "Configuration file for the AnyLogic agent",
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
        Path("client").mkdir(parents=True, exist_ok=True)
        _generate_files(files_to_generate, existing_files, created_files)
        _print_summary(created_files, existing_files, file_descriptions)
    except FileNotFoundError:
        print("❌ Error: One or more template files were not found.")
    except Exception as e:
        print(f"❌ Error generating project files: {e}")


def _generate_files(files_to_generate, existing_files, created_files):
    """Generate files using either importlib.resources or pkg_resources."""
    try:
        from importlib.resources import files
        _copy_files_with_importlib(
            files_to_generate,
            existing_files,
            created_files,
            files)
    except (ImportError, AttributeError):
        _copy_files_with_pkg_resources(
            files_to_generate, existing_files, created_files)


def _copy_files_with_importlib(
        files_to_generate, existing_files, created_files, files):
    """Copy files using importlib.resources."""
    for output_name, (package, resource_name) in files_to_generate.items():
        if _should_skip_existing(output_name, existing_files):
            continue

        output_path = Path(output_name)
        resource_path = files(package).joinpath(resource_name)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(resource_path, 'rb') as src, open(output_path, 'wb') as dst:
            dst.write(src.read())
        created_files.append(output_name)


def _copy_files_with_pkg_resources(
        files_to_generate, existing_files, created_files):
    """Copy files using pkg_resources."""
    import pkg_resources

    for output_name, (package, resource_name) in files_to_generate.items():
        if _should_skip_existing(output_name, existing_files):
            continue

        output_path = Path(output_name)
        template_content = pkg_resources.resource_string(package, resource_name)

        with open(output_path, 'wb') as dst:
            dst.write(template_content)
        created_files.append(output_name)


def _should_skip_existing(output_name, existing_files):
    """Check if file exists and add to existing_files list if so."""
    output_path = Path(output_name)
    if output_path.exists():
        existing_files.append(output_name)
        return True
    return False


def _print_summary(created_files, existing_files, file_descriptions):
    """Print summary of created and existing files."""
    print("\nProject generation summary:\n")

    if created_files:
        print("🆕 Files created:")
        _print_file_list(created_files, file_descriptions)

    if existing_files:
        print("\n📄 Files already present (skipped):")
        _print_file_list(existing_files, file_descriptions)

    _print_completion_message(created_files)


def _print_file_list(files, file_descriptions):
    """Print a list of files with their descriptions."""
    for f in files:
        description = file_descriptions.get(f, "No description available")
        print(f" - {f:<35} : {description}")


def _print_completion_message(created_files):
    """Print appropriate completion message based on whether files were created."""
    if not created_files:
        print("\nAll project files already exist. Nothing was created.")
    else:
        print("\nYou can now customize these files as needed and start using the AnyLogic agent.")


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
