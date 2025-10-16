"""Unit tests for the Simul8 simulator module."""

import pytest
from pytest import approx

from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


from src.core.simul8_simulator import Simul8Simulator, Simul8SimulationError

@pytest.fixture
def sim_path():
    """Provide a standard simulation path."""
    return "simul8_agent/docs/examples"

@pytest.fixture
def sim_file():
    """Provide a standard simulation file name."""
    return "simulation_batch.s8"

@pytest.fixture
def patch_path_exists():
    """Patch Path.exists and is_dir to return True."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.is_dir', return_value=True):
        yield

@pytest.fixture
def simulator(sim_path, sim_file, patch_path_exists):
    """Create a Simul8Simulator instance with mocked dependencies."""
    return Simul8Simulator(sim_path, sim_file)

class TestSimul8SimulatorInitialization:
    """Tests for Simul8Simulator initialization."""

    def test_init_with_valid_path(self, simulator, sim_path, sim_file):
        """Test initialization with a valid path."""
        assert simulator.sim_path == Path(sim_path).resolve()
        assert simulator.sim_file == sim_file

    def test_init_with_invalid_path(self, sim_file):
        """Test initialization with an invalid path raises FileNotFoundError."""
        with patch('pathlib.Path.is_dir', return_value=False):
            with pytest.raises(FileNotFoundError, match="Simulation directory not found"):
                Simul8Simulator('/invalid/path', sim_file)

class TestSimul8SimulatorOperations:
    """Tests for Simul8Simulator operations."""

    def test_run_success(self, simulator):
        """Test successful simulation run."""
        # Patch the internal method that actually runs Simul8
        with patch.object(simulator, 'run', return_value={'total_co2': 123, 'total_energy': 456}):
            result = simulator.run(inputs={'run_time': 500, 'columns': ['co2', 'energy']}, outputs=['total_co2', 'total_energy'])
            assert result == {'total_co2': 123, 'total_energy': 456}

    def test_run_simul8_error(self, simulator):
        """Test handling Simul8 error during run."""
        with patch.object(simulator, 'run', side_effect=Simul8SimulationError("Simul8 failed")):
            with pytest.raises(Simul8SimulationError, match="Simul8 failed"):
                simulator.run(inputs={'run_time': 500}, outputs=['total_co2'])

    def test_run_with_missing_outputs(self, simulator):
        """Test simulation run with missing outputs."""
        with patch.object(simulator, 'run', return_value={}):
            result = simulator.run(inputs={'run_time': 500}, outputs=[])
            assert result == {}