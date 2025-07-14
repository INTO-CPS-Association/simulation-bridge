"""Global test fixtures."""
from pathlib import Path
import yaml
import pytest

@pytest.fixture(scope="session")
def dummy_credentials():
    """Load dummy credentials for tests from YAML file."""
    cred_file = Path(__file__).parent / "config" / "credentials.yaml.tests"
    with open(cred_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
