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

class TestSimul8SimulatorMetadata:
    """Tests for Simul8Simulator metadata functionality."""

    def test_get_metadata(self, simulator):
        """Test getting metadata."""
        # Patch psutil and time if used in your implementation
        with patch('psutil.Process') as mock_process, patch('time.time', return_value=1000):
            mock_memory_info = Mock()
            mock_memory_info.rss = 100 * 1024 * 1024  # 100 MB
            mock_process.return_value.memory_info.return_value = mock_memory_info
            metadata = simulator.get_metadata()
        assert 'memory_usage' in metadata

    def test_get_metadata_with_execution_time(self, simulator):
        """Test getting metadata with execution time."""
        simulator.start_time = 1000
        with patch('psutil.Process') as mock_process, patch('time.time', return_value=1010):
            mock_memory_info = Mock()
            mock_memory_info.rss = 120 * 1024 * 1024  # 120 MB
            mock_process.return_value.memory_info.return_value = mock_memory_info
            metadata = simulator.get_metadata()
        assert metadata['execution_time'] ==  approx(10.0, rel=1e-9, abs=1e-9)
        assert metadata['memory_usage'] == approx(120, rel=1e-9, abs=1e-9)
