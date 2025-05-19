"""
Entry point module for running the MATLAB Agent with default configuration.
This module provides a simplified interface for running the agent without command-line arguments.
"""

from .main import main


def run():
    """
    Entry point for the package when installed.
    Runs the main function without requiring command-line arguments and uses
    the default agent_id from the config.
    """
    main()


if __name__ == "__main__":
    run()
