"""
Utility functions for generating default project files and configuration.
"""

import os

try:
    from importlib.resources import files # only available in Python 3.9+
    pkg_resources = None  # pylint: disable=invalid-name
except ImportError:
    files = None
    import pkg_resources

CONFIG_FILENAME = 'config.yaml'
CONFIG_TEMPLATE_FILENAME = 'config.yaml.template'
CONFIG_PATH = 'simulation_bridge.config'


def copy_resource(package, resource, target_path):
    """Copy a resource file to the given target path."""
    try:
        if files:
            template_path = files(package).joinpath(resource)
            with open(template_path, 'rb') as src, open(target_path, 'wb') as dst:
                dst.write(src.read())
        else:
            template_content = pkg_resources.resource_string(package, resource)
            with open(target_path, 'wb') as dst:
                dst.write(template_content)
        return True
    except (FileNotFoundError, OSError, IOError):
        return False


def create_directory(file_path, full_path):
    """Create a directory and return status."""
    if os.path.exists(full_path):
        print(f"Directory already exists: {file_path}")
        return 'skipped', None
    try:
        os.makedirs(full_path, exist_ok=True)
        print(f"✓ Created directory: {file_path}")
        return 'created', None
    except OSError as error:
        error_msg = f"Failed to create directory {file_path}: {error}"
        print(f"✗ {error_msg}")
        return 'error', error_msg


def create_file(file_path, full_path, package, resource):
    """Create a file and return status."""
    if os.path.exists(full_path):
        print(f"File already exists (skipping): {file_path}")
        return 'skipped', None

    parent_dir = os.path.dirname(full_path)
    if parent_dir and not os.path.exists(parent_dir):
        try:
            os.makedirs(parent_dir, exist_ok=True)
        except OSError as error:
            error_msg = f"Failed to create parent directory for {file_path}: {error}"
            print(f"✗ {error_msg}")
            return 'error', error_msg

    if copy_resource(package, resource, full_path):
        print(f"✓ Created file: {file_path}")
        return 'created', None

    error_msg = f"Failed to create {file_path} from {package}/{resource}"
    print(f"✗ {error_msg}")
    return 'error', error_msg


def print_summary(created, skipped, errors, descriptions):
    """Print a summary of the project generation results."""
    print("-" * 50)
    print("Project generation summary:")
    print(f"✓ Created: {len(created)} files/directories")
    print(f"⏭ Skipped: {len(skipped)} files/directories (already exist)")
    print(f"✗ Errors: {len(errors)} files/directories")

    if created:
        print("\nCreated files and directories:")
        for item in created:
            description = descriptions.get(item, "")
            print(f"  • {item} - {description}")

    if skipped:
        print("\nSkipped files and directories:")
        for item in skipped:
            description = descriptions.get(item, "")
            print(f"  • {item} - {description}")

    if errors:
        print("\nErrors encountered:")
        for error in errors:
            print(f"  • {error}")

    print("\nProject structure generated successfully!")


def get_files_to_generate():
    """Return the dictionary of files to generate."""
    return {
        CONFIG_FILENAME: (CONFIG_PATH, CONFIG_TEMPLATE_FILENAME),
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


def get_file_descriptions():
    """Return the dictionary of file descriptions."""
    return {
        CONFIG_FILENAME: "Main configuration file for the simulation bridge",
        'client/simulation.yaml': "Example payload for simulation requests",
        'client/mqtt/mqtt_client.py': "MQTT protocol client implementation",
        'client/mqtt/mqtt_use.yaml': "MQTT usage configuration (example)",
        'client/rabbitmq/rabbitmq_client.py': "RabbitMQ protocol client implementation",
        'client/rabbitmq/rabbitmq_use.yaml': "RabbitMQ usage configuration (example)",
        'client/rest/rest_client.py': "REST protocol client implementation",
        'client/rest/rest_use.yaml': "REST usage configuration (example)",
    }


def copy_config_template(config_path):
    """Copy configuration template using available import method."""
    try:
        if files:
            template_path = files(CONFIG_PATH).joinpath(
                CONFIG_TEMPLATE_FILENAME)
            with open(template_path, 'rb') as src, open(config_path, 'wb') as dst:
                dst.write(src.read())
        else:
            template_content = pkg_resources.resource_string(
                CONFIG_PATH, CONFIG_TEMPLATE_FILENAME)
            with open(config_path, 'wb') as dst:
                dst.write(template_content)
    except (ImportError, AttributeError, FileNotFoundError) as e:
        raise FileNotFoundError(f"Template configuration file not found: {e}") from e


def generate_default_config():
    """Copy the template configuration file to the current directory if not already present."""
    config_path = os.path.join(os.getcwd(), CONFIG_FILENAME)
    if os.path.exists(config_path):
        print(f"File already exists at path: {config_path}")
        return

    try:
        copy_config_template(config_path)
        print(f"Configuration template copied to: {config_path}")
    except FileNotFoundError:
        print("Error: Template configuration file not found.")
    except (OSError, IOError) as e:
        print(f"Error generating configuration file: {e}")


def generate_default_project():
    """Generate default project files and directories in the current directory."""
    files_to_generate = get_files_to_generate()
    file_descriptions = get_file_descriptions()
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
            status, error = create_directory(file_path, full_path)
        else:
            status, error = create_file(
                file_path, full_path, package, resource)

        if status == 'created':
            created_files.append(file_path)
        elif status == 'skipped':
            skipped_files.append(file_path)
        elif status == 'error' and error:
            errors.append(error)

    print_summary(created_files, skipped_files, errors, file_descriptions)
