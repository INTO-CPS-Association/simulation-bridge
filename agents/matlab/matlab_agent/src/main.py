"""
Main entry point for the MATLAB Agent application.
"""
import os
import logging
import click
from .utils.logger import setup_logger
from .interfaces.agent import IMatlabAgent
from .core.agent import MatlabAgent
from .utils.config_loader import load_config


@click.command()
@click.option('--config-file', '-c', type=click.Path(exists=True),
              default=None, help='Path to custom configuration file')
@click.option('--generate-config', is_flag=True,
              help='Generate a default configuration file in the current directory')
@click.option('--generate-project', is_flag=True,
              help='Generate default project files in the current directory')
def main(config_file=None, generate_config=False, generate_project=False) -> None:
    """
    Main function to initialize and start the MATLAB agent.
    Supports single or multiple agents with different configurations.
    """
    if generate_config:
        generate_default_config()
        return
    if generate_project:
        generate_default_project()
        return
    if config_file:
        run_single_agent(config_file)
    else:
        if not os.path.exists('config.yaml'):
            print("""
Error: Configuration file 'config.yaml' not found.

To generate a default configuration file, run:
matlab-agent --generate-config
       
You may customize the generated file as needed and re-run the program.

Alternatively, if you already have a custom configuration file, use the 
--config-file option to specify its path:
matlab-agent --config-file /path/to/your/config.yaml
        """)
            return
        else:
            run_single_agent('config.yaml')
        
def generate_default_config():
    """Copy the template configuration file to the current directory."""
    try:
        try:
            from importlib.resources import files
            template_path = files('matlab_agent.config').joinpath(
                'config.yaml.template')
            with open(template_path, 'rb') as src, open('config.yaml', 'wb') as dst:
                dst.write(src.read())
        except (ImportError, AttributeError):
            import pkg_resources
            template_content = pkg_resources.resource_string(
                'matlab_agent.config', 'config.yaml.template')
            with open('config.yaml', 'wb') as dst:
                dst.write(template_content)
        print(
            f"Configuration template copied to: {os.path.join(os.getcwd(), 'config.yaml')}")
    except FileNotFoundError:
        print("Error: Template configuration file not found.")
    except Exception as e:
        print(f"Error generating configuration file: {e}")

def generate_default_project():
    """Copy the template configuration file to the current directory."""
    try:
        try:
            from importlib.resources import files
            config_template_path = files('matlab_agent.config').joinpath(
                'config.yaml.template')
            with open(config_template_path, 'rb') as src, open('config.yaml', 'wb') as dst:
                dst.write(src.read())
            wrapper_template_path = files('matlab_agent.resources').joinpath(
                'SimulationWrapper.m')
            with open(wrapper_template_path, 'rb') as src, open('SimulationWrapper.m', 'wb') as dst:
                dst.write(src.read())
            batch_template_path = files('matlab_agent.docs.examples').joinpath(
                'simulation_batch.m.template')
            with open(batch_template_path, 'rb') as src, open('SimulationBatch.m', 'wb') as dst:
                dst.write(src.read())
            streaming_template_path = files('matlab_agent.docs.examples').joinpath(
                'simulation_streaming.m.template')
            with open(streaming_template_path, 'rb') as src, open('SimulationStreaming.m', 'wb') as dst:
                dst.write(src.read())
        except (ImportError, AttributeError):
            import pkg_resources
            template_content = pkg_resources.resource_string(
                'matlab_agent.config', 'config.yaml.template')
            with open('config.yaml', 'wb') as dst:
                dst.write(template_content)
        print(
    "Project files generated successfully in the current directory:\n"
    " - config.yaml\n"
    " - SimulationWrapper.m\n"
    " - SimulationBatch.m\n"
    " - SimulationStreaming.m\n\n"
    "You can now customize these files as needed and run the MATLAB agent.")
    except FileNotFoundError:
        print("Error: Template configuration file not found.")
    except Exception as e:
        print(f"Error generating configuration file: {e}")



def run_single_agent(config_file):
    """Initializes and starts a single MATLAB agent instance."""
    broker_type = "rabbitmq"
    config = load_config(config_file)
    logging_level = config['logging']['level']
    logging_file = config['logging']['file']

    logger: logging.Logger = setup_logger(
        level=getattr(logging, logging_level.upper(), logging.INFO),
        log_file=logging_file)

    agent_id = config['agent']['agent_id']
    agent: IMatlabAgent = MatlabAgent(
        agent_id,
        broker_type=broker_type,
        config_path=config_file)

    try:
        logger.debug("Starting MATLAB agent with config: %s", config)
        agent.start()
    except KeyboardInterrupt:
        logger.info("Shutting down agent due to keyboard interrupt")
        agent.stop()
    except Exception as e:
        logger.error("Error running agent: %s", e)
        agent.stop()


if __name__ == "__main__":
    main()
