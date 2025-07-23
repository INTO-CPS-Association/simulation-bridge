"""Global test fixtures and monkey patches for tests."""
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock

import yaml
import pytest

# ---------------------------------------------------------------------------
# Monkey patch the ``matlab`` module so that tests can run without a real
# MATLAB installation.  The project code imports ``matlab.engine`` at module
# load time, which normally requires the MATLAB Python package to be
# available.  In CI environments this package is often missing, so we
# provide a lightweight stand-in with the minimal structure required by the
# tests.  Individual tests can still patch specific functions like
# ``start_matlab`` or ``matlab.double`` as needed.
# ---------------------------------------------------------------------------
if "matlab" not in sys.modules:
    matlab_mod = types.ModuleType("matlab")
    engine_mod = types.ModuleType("engine")

    class DummyMatlabDouble(list):
        """Lightweight substitute for matlab.double used in tests."""
        pass

    matlab_mod.double = DummyMatlabDouble
    engine_mod.MatlabEngine = MagicMock
    engine_mod.EngineError = Exception
    engine_mod.start_matlab = MagicMock()

    matlab_mod.engine = engine_mod
    sys.modules["matlab"] = matlab_mod
    sys.modules["matlab.engine"] = engine_mod


@pytest.fixture(scope="session")
def dummy_credentials():
    """Load dummy credentials for tests from YAML file."""
    cred_file = Path(__file__).parent / "config" / "credentials.yaml.tests"
    with open(cred_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
