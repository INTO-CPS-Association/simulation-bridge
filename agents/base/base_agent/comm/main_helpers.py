"""Shared helpers for simulator-agent CLI entry points and project scaffolding."""

# pylint: disable=import-outside-toplevel,too-many-arguments,too-many-positional-arguments

from pathlib import Path
from typing import Callable


def print_missing_config_message(command_name: str) -> None:
    """Print the standard guidance shown when config.yaml is missing."""
    print(f"""
Error: Configuration file 'config.yaml' not found.

To generate a default configuration file, run:
{command_name} --generate-config

You may customize the generated file as needed and re-run the program.

Alternatively, if you already have a custom configuration file, use the
--config-file option to specify its path:
{command_name} --config-file /path/to/your/config.yaml
        """)


def run_main_with_default_config(
    config_file: str | None,
    generate_config: bool,
    generate_project: bool,
    generate_config_func: Callable[[], None],
    generate_project_func: Callable[[], None],
    run_agent_func: Callable[[str], None],
    command_name: str,
) -> None:
    """Execute shared CLI flow for generate flags and default config resolution."""
    if generate_config:
        generate_config_func()
        return
    if generate_project:
        generate_project_func()
        return
    if config_file:
        run_agent_func(config_file)
        return

    config_path = Path("config.yaml")
    if not config_path.exists():
        print_missing_config_message(command_name)
        return

    run_agent_func(str(config_path))


def copy_packaged_resource(package_name: str, resource_name: str, output_path: Path) -> None:
    """Copy a package resource to a local output path with importlib/pkg_resources fallback."""
    try:
        from importlib.resources import files

        resource_path = files(package_name).joinpath(resource_name)
        with open(resource_path, "rb") as src, open(output_path, "wb") as dst:
            dst.write(src.read())
    except (ImportError, AttributeError):
        # pylint: disable=import-outside-toplevel
        import pkg_resources

        resource_content = pkg_resources.resource_string(package_name, resource_name)
        with open(output_path, "wb") as dst:
            dst.write(resource_content)


def generate_project_files(
    files_to_generate: dict[str, tuple[str, str]],
) -> tuple[list[str], list[str]]:
    """Generate project files and return created/existing file lists."""
    existing_files: list[str] = []
    created_files: list[str] = []

    for output_name, (package_name, resource_name) in files_to_generate.items():
        output_path = Path(output_name)
        if output_path.exists():
            existing_files.append(output_name)
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)
        copy_packaged_resource(package_name, resource_name, output_path)
        created_files.append(output_name)

    return created_files, existing_files
