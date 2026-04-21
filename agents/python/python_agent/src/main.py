"""Main entry point for the Python Agent application."""

from pathlib import Path
import logging
from importlib.resources import files

import click

from .core.agent import PythonAgent
from .interfaces.agent import IPythonAgent
from .utils.config_loader import load_config
from .utils.logger import setup_logger


@click.command()
@click.option(
    "--config-file",
    "-c",
    type=click.Path(exists=True),
    default=None,
    help="Path to custom configuration file",
)
@click.option(
    "--generate-config",
    is_flag=True,
    help="Generate a default configuration file in the current directory",
)
@click.option(
    "--generate-project",
    is_flag=True,
    help="Generate default project files in the current directory",
)
def main(config_file=None, generate_config=False, generate_project=False) -> None:
    """An agent service to execute generic scripts/programs via CLI arguments."""
    if generate_config:
        generate_default_config()
        return
    if generate_project:
        generate_default_project()
        return
    if config_file:
        run_agent(config_file)
        return

    config_path = Path("config.yaml")
    if not config_path.exists():
        print(
            """
Error: Configuration file 'config.yaml' not found.

To generate a default configuration file, run:
python-agent --generate-config

Alternatively, specify an existing config path:
python-agent --config-file /path/to/your/config.yaml
        """
        )
        return

    run_agent(str(config_path))


def generate_default_config() -> None:
    """Copy the default config template if missing."""
    config_path = Path.cwd() / "config.yaml"
    if config_path.exists():
        print(f"File already exists at path: {config_path}")
        return

    try:
        template_path = files("python_agent.config").joinpath("config.yaml.template")
        with open(template_path, "rb") as src, open(config_path, "wb") as dst:
            dst.write(src.read())
        print(f"Configuration template copied to: {config_path}")
    except FileNotFoundError:
        print("Error: Template configuration file not found.")


def generate_default_project() -> None:
    """Generate a minimal runnable project scaffold for the Python Agent."""
    files_to_generate = {
        "config.yaml": ("python_agent.config", "config.yaml.template"),
        "scripts/example_cli_program.py": ("python_agent.resources", "example_cli_program.py"),
        "client/use_python_agent_batch.py": ("python_agent.resources", "use_python_agent_batch.py"),
        "client/use.yaml": ("python_agent.resources", "use.yaml.template"),
        "client/simulation.yaml": ("python_agent.api", "simulation.yaml.template"),
        "client/README.md": ("python_agent.resources", "README.md"),
    }

    created_files = []
    existing_files = []

    for output_name, (package, resource_name) in files_to_generate.items():
        output_path = Path(output_name)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists():
            existing_files.append(output_name)
            continue

        resource_path = files(package).joinpath(resource_name)
        with open(resource_path, "rb") as src, open(output_path, "wb") as dst:
            dst.write(src.read())
        created_files.append(output_name)

    print("\nProject generation summary:\n")
    if created_files:
        print("🆕 Files created:")
        for file_name in created_files:
            print(f" - {file_name}")
    if existing_files:
        print("\n📄 Files already present (skipped):")
        for file_name in existing_files:
            print(f" - {file_name}")


def run_agent(config_file) -> None:
    """Initialize and start a single Python agent instance."""
    config = load_config(config_file)
    logging_level = config["logging"]["level"]
    logging_file = config["logging"]["file"]

    logger: logging.Logger = setup_logger(
        level=getattr(logging, logging_level.upper(), logging.INFO),
        log_file=logging_file,
    )

    agent_id = config["agent"]["agent_id"]
    agent: IPythonAgent = PythonAgent(
        agent_id,
        broker_type="rabbitmq",
        config_path=config_file,
    )

    try:
        logger.debug("Starting python agent with config: %s", config)
        agent.start()
    except KeyboardInterrupt:
        logger.info("Shutting down agent due to keyboard interrupt")
        agent.stop()
    except Exception as error:  # pylint: disable=broad-except
        logger.error("Error running agent: %s", error)
        agent.stop()


if __name__ == "__main__":
    main()
