"""
Simulation Bridge entry point.
"""
import logging
import os

import click

from .core.bridge_orchestrator import BridgeOrchestrator
from .utils.config_loader import load_config
from .utils.logger import setup_logger

CONFIG_FILENAME = 'config.yaml'
CONFIG_TEMPLATE_FILENAME = 'config.yaml.template'
CONFIG_PATH = 'simulation_bridge.config'
CERTS_PATH = 'certs/'


@click.command()
@click.option('--config-file', '-c', type=click.Path(exists=True),
              default=None, help='Path to custom configuration file')
@click.option('--generate-config', is_flag=True,
              help='Generate a default configuration file in the current directory')
@click.option('--generate-project', is_flag=True,
              help='Generate default project files in the current directory')
def main(config_file=None, generate_config=False,
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
    except OSError as e:
        logger.error("OS error: %s", str(e), exc_info=True)
        bridge.stop()
    except ValueError as e:
        logger.error("Configuration error: %s", str(e), exc_info=True)
        bridge.stop()


def generate_default_config():
    """Copy the template configuration file to the current directory if not already present."""
    config_path = os.path.join(os.getcwd(), CONFIG_FILENAME)
    if os.path.exists(config_path):
        print(f"File already exists at path: {config_path}")
        return

    try:
        _copy_config_template(config_path)
        print(f"Configuration template copied to: {config_path}")
    except FileNotFoundError:
        print("Error: Template configuration file not found.")
    except (OSError, IOError) as e:
        print(f"Error generating configuration file: {e}")


def _copy_config_template(config_path):
    """Copy configuration template using available import method."""
    try:
        # pylint: disable=import-outside-toplevel
        from importlib.resources import files
        template_path = files(CONFIG_PATH).joinpath(
            CONFIG_TEMPLATE_FILENAME)
        with open(template_path, 'rb') as src, open(config_path, 'wb') as dst:
            dst.write(src.read())
    except (ImportError, AttributeError):
        # pylint: disable=import-outside-toplevel
        import pkg_resources
        template_content = pkg_resources.resource_string(CONFIG_PATH,
                                                         CONFIG_TEMPLATE_FILENAME)
        with open(config_path, 'wb') as dst:
            dst.write(template_content)


def _copy_resource(package, resource, target_path):
    """Helper to copy a resource file to target path."""
    try:
        try:
            # pylint: disable=import-outside-toplevel
            from importlib.resources import files
            template_path = files(package).joinpath(resource)
            with open(template_path, 'rb') as src, open(target_path, 'wb') as dst:
                dst.write(src.read())
            return True
        except (ImportError, AttributeError):
            # pylint: disable=import-outside-toplevel
            import pkg_resources
            template_content = pkg_resources.resource_string(package, resource)
            with open(target_path, 'wb') as dst:
                dst.write(template_content)
            return True
    except FileNotFoundError:
        return False
    except (OSError, IOError):
        return False


def _get_files_to_generate():
    """Return the dictionary of files to generate."""
    return {
        CONFIG_FILENAME: (CONFIG_PATH, CONFIG_TEMPLATE_FILENAME),
        CERTS_PATH: ('', CERTS_PATH),
        'client/simulation.yaml': ('simulation_bridge.resources',
                                   'simulation.yaml.template'),
        'client/mqtt/mqtt_client.py': ('simulation_bridge.resources.mqtt',
                                       'mqtt_client.py'),
        'client/mqtt/mqtt_use.yaml': ('simulation_bridge.resources.mqtt',
                                      'mqtt_use.yaml.template'),
        'client/rabbitmq/rabbitmq_client.py': ('simulation_bridge.resources.rabbitmq',
                                               'rabbitmq_client.py'),
        'client/rabbitmq/rabbitmq_use.yaml': ('simulation_bridge.resources.rabbitmq',
                                              'rabbitmq_use.yaml.template'),
        'client/rest/rest_client.py': ('simulation_bridge.resources.rest',
                                       'rest_client.py'),
        'client/rest/rest_use.yaml': ('simulation_bridge.resources.rest',
                                      'rest_use.yaml.template'),
    }


def _get_file_descriptions():
    """Return the dictionary of file descriptions."""
    return {
        CONFIG_FILENAME: "Main configuration file for the simulation bridge",
        CERTS_PATH: "Directory for storing TLS certificates (create manually if needed)",
        'client/simulation.yaml': "Example payload for simulation requests",
        'client/mqtt/mqtt_client.py': "MQTT protocol client implementation",
        'client/mqtt/mqtt_use.yaml': "MQTT usage configuration (example)",
        'client/rabbitmq/rabbitmq_client.py': "RabbitMQ protocol client implementation",
        'client/rabbitmq/rabbitmq_use.yaml': "RabbitMQ usage configuration (example)",
        'client/rest/rest_client.py': "REST protocol client implementation",
        'client/rest/rest_use.yaml': "REST usage configuration (example)",
    }


def _create_directory(file_path, full_path):
    """Create a directory and return status."""
    if os.path.exists(full_path):
        print(f"Directory already exists: {file_path}")
        return 'skipped', None

    try:
        os.makedirs(full_path, exist_ok=True)
        print(f"✓ Created directory: {file_path}")
        return 'created', None
    except OSError as e:
        error_msg = f"Failed to create directory {file_path}: {e}"
        print(f"✗ {error_msg}")
        return 'error', error_msg


def _create_file(file_path, full_path, package, resource):
    """Create a file and return status."""
    if os.path.exists(full_path):
        print(f"File already exists (skipping): {file_path}")
        return 'skipped', None

    # Create parent directories if needed
    parent_dir = os.path.dirname(full_path)
    if parent_dir and not os.path.exists(parent_dir):
        try:
            os.makedirs(parent_dir, exist_ok=True)
        except OSError as e:
            error_msg = f"Failed to create parent directory for {file_path}: {e}"
            print(f"✗ {error_msg}")
            return 'error', error_msg

    # Copy resource file
    if _copy_resource(package, resource, full_path):
        print(f"✓ Created file: {file_path}")
        return 'created', None

    error_msg = f"Failed to create {file_path} from {package}/{resource}"
    print(f"✗ {error_msg}")
    return 'error', error_msg


def _print_summary(created_files, skipped_files, errors, file_descriptions):
    """Print generation summary."""
    print("-" * 50)
    print("Project generation summary:")
    print(f"✓ Created: {len(created_files)} files/directories")
    print(f"⏭ Skipped: {len(skipped_files)} files/directories (already exist)")
    print(f"✗ Errors: {len(errors)} files/directories")

    if created_files:
        print("\nCreated files and directories:")
        for item in created_files:
            description = file_descriptions.get(item, "")
            print(f"  • {item} - {description}")

    if skipped_files:
        print("\nSkipped files and directories:")
        for item in skipped_files:
            description = file_descriptions.get(item, "")
            print(f"  • {item} - {description}")

    if errors:
        print("\nErrors encountered:")
        for error in errors:
            print(f"  • {error}")

    print("\nProject structure generated successfully!")


def generate_default_project():
    """Generate default project files and directories in the current directory."""
    files_to_generate = _get_files_to_generate()
    file_descriptions = _get_file_descriptions()
    current_dir = os.getcwd()

    created_files = []
    skipped_files = []
    errors = []

    print("Generating default project structure...")
    print(f"Target directory: {current_dir}")
    print("-" * 50)

    for file_path, (package, resource) in files_to_generate.items():
        full_path = os.path.join(current_dir, file_path)

        if file_path.endswith('/'):
            status, error = _create_directory(file_path, full_path)
        else:
            status, error = _create_file(
                file_path, full_path, package, resource)

        if status == 'created':
            created_files.append(file_path)
        elif status == 'skipped':
            skipped_files.append(file_path)
        elif status == 'error' and error:
            errors.append(error)

    _print_summary(created_files, skipped_files, errors, file_descriptions)


if __name__ == "__main__":
    main()
