"""
Simulation Bridge entry point.
"""
import os
from .core.bridge_orchestrator import BridgeOrchestrator
from .utils.logger import setup_logger
from .utils.config_loader import load_config
import click
import sys
from pathlib import Path

import logging


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


def generate_default_project():
    """Generate default project files and directories in the current directory."""

    files_to_generate = {
        'config.yaml': ('simulation_bridge.config', 'config.yaml.template'),

        # Certificates directory
        'certs/': ('', 'certs/'),

        # Simulation payload example
        'client/simulation.yaml': ('simulation_bridge.resources', 'simulation.yaml.template'),

        # MQTT adapter client and usage example
        'client/mqtt/mqtt_client.py': ('simulation_bridge.resources.mqtt', 'mqtt_client.py'),
        'client/mqtt/mqtt_use.yaml': ('simulation_bridge.resources.mqtt', 'mqtt_use.yaml.template'),

        # RabbitMQ adapter client and usage example
        'client/rabbitmq/rabbitmq_client.py': ('simulation_bridge.resources.rabbitmq', 'rabbitmq_client.py'),
        'client/rabbitmq/rabbitmq_use.yaml': ('simulation_bridge.resources.rabbitmq', 'rabbitmq_use.yaml.template'),

        # REST adapter client and usage example
        'client/rest/rest_client.py': ('simulation_bridge.resources.rest', 'rest_client.py'),
        'client/rest/rest_use.yaml': ('simulation_bridge.resources.rest', 'rest_use.yaml.template'),
    }

    # Updated file descriptions
    file_descriptions = {
        'config.yaml': "Main configuration file for the simulation bridge",
        'certs/': "Directory for storing TLS certificates (create manually if needed)",
        'client/simulation.yaml': "Example payload for simulation requests",
        'client/mqtt/mqtt_client.py': "MQTT protocol client implementation",
        'client/mqtt/mqtt_use.yaml': "MQTT usage configuration (example)",
        'client/rabbitmq/rabbitmq_client.py': "RabbitMQ protocol client implementation",
        'client/rabbitmq/rabbitmq_use.yaml': "RabbitMQ usage configuration (example)",
        'client/rest/rest_client.py': "REST protocol client implementation",
        'client/rest/rest_use.yaml': "REST usage configuration (example)",
    }

    current_dir = os.getcwd()
    created_files = []
    skipped_files = []
    errors = []

    print("Generating default project structure...")
    print(f"Target directory: {current_dir}")
    print("-" * 50)

    for file_path, (package, resource) in files_to_generate.items():
        full_path = os.path.join(current_dir, file_path)

        # Handle directory creation (certs/)
        if file_path.endswith('/'):
            if os.path.exists(full_path):
                print(f"Directory already exists: {file_path}")
                skipped_files.append(file_path)
            else:
                try:
                    os.makedirs(full_path, exist_ok=True)
                    print(f"✓ Created directory: {file_path}")
                    created_files.append(file_path)
                except Exception as e:
                    error_msg = f"Failed to create directory {file_path}: {e}"
                    print(f"✗ {error_msg}")
                    errors.append(error_msg)
            continue

        # Handle file creation
        if os.path.exists(full_path):
            print(f"File already exists (skipping): {file_path}")
            skipped_files.append(file_path)
            continue

        # Create parent directories if they don't exist
        parent_dir = os.path.dirname(full_path)
        if parent_dir and not os.path.exists(parent_dir):
            try:
                os.makedirs(parent_dir, exist_ok=True)
            except Exception as e:
                error_msg = f"Failed to create parent directory for {file_path}: {e}"
                print(f"✗ {error_msg}")
                errors.append(error_msg)
                continue

        # Copy file from package resources
        try:
            # Try new importlib.resources approach first
            try:
                from importlib.resources import files
                template_path = files(package).joinpath(resource)
                with open(template_path, 'rb') as src, open(full_path, 'wb') as dst:
                    dst.write(src.read())
            except (ImportError, AttributeError):
                # Fallback to pkg_resources for older Python versions
                import pkg_resources
                template_content = pkg_resources.resource_string(
                    package, resource)
                with open(full_path, 'wb') as dst:
                    dst.write(template_content)

            print(f"✓ Created file: {file_path}")
            created_files.append(file_path)

        except FileNotFoundError:
            error_msg = f"Template not found for {file_path} (package: {package}, resource: {resource})"
            print(f"✗ {error_msg}")
            errors.append(error_msg)
        except Exception as e:
            error_msg = f"Failed to create {file_path}: {e}"
            print(f"✗ {error_msg}")
            errors.append(error_msg)

    # Print summary
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


if __name__ == "__main__":
    main()
