from .main import main
from .utils.config_loader import load_config

def run():
    """
    Entry point for the package when installed.
    Runs the main function without requiring command-line arguments and uses the default agent_id from the config.
    """
    main() 

if __name__ == "__main__":
    run()