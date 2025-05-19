"""
Unit tests for run_default_agent.py module which provides the default entry point
for the MATLAB Agent.
"""
from src.run_default_agent import run
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

# Add the parent directory to sys.path to enable importing the module under test
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the module to be tested


class TestRunDefaultAgent:
    """Test cases focusing exclusively on the run_default_agent.py functionality."""

    @patch('src.run_default_agent.main')
    def test_run_calls_main(self, mock_main):
        """
        Test that the run() function calls the main() function from the main module.
        This is the only functionality in run_default_agent.py that needs testing.
        """
        # Call the function under test
        run()

        # Verify that main was called exactly once with no arguments
        mock_main.assert_called_once_with()
