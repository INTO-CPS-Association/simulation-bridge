"""Unit tests for the MATLAB simulator module."""

import pytest
from pytest import approx
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.core.matlab_simulator import MatlabSimulator, MatlabSimulationError


@pytest.fixture
def sim_path():
    """Provide a standard simulation path."""
    return "matlab_agent/docs/examples"


@pytest.fixture
def sim_file():
    """Provide a standard simulation file name."""
    return "simulation_batch.m"


@pytest.fixture
def mock_matlab_engine():
    """Provide a mock MATLAB engine."""
    with patch('matlab.engine.start_matlab') as mock_start:
        mock_engine = Mock()
        mock_start.return_value = mock_engine
        yield mock_engine


@pytest.fixture
def patch_path_exists():
    """Patch Path.exists and is_dir to return True."""
    with patch('pathlib.Path.exists', return_value=True), \
            patch('pathlib.Path.is_dir', return_value=True):
        yield


@pytest.fixture
def simulator(sim_path, sim_file, patch_path_exists):
    """Create a MatlabSimulator instance with mocked dependencies."""
    return MatlabSimulator(sim_path, sim_file)


@pytest.fixture
def running_simulator(simulator, mock_matlab_engine):
    """Create a simulator that is ready to run simulations."""
    simulator.eng = mock_matlab_engine
    simulator.start_time = 0
    return simulator


class TestMatlabSimulatorInitialization:
    """Tests for MatlabSimulator initialization."""

    def test_init_with_valid_path(self, simulator, sim_path, sim_file):
        """Test initialization with a valid path."""
        assert simulator.sim_path == Path(sim_path).resolve()
        assert simulator.function_name == "simulation_batch"
        assert simulator.eng is None

    def test_init_with_custom_function_name(
            self, sim_path, sim_file, patch_path_exists):
        """Test initialization with a custom function name."""
        simulator = MatlabSimulator(sim_path, sim_file, "custom_function")
        assert simulator.function_name == "custom_function"

    def test_init_with_invalid_path(self, sim_file):
        """Test initialization with an invalid path raises FileNotFoundError."""
        with patch('pathlib.Path.is_dir', return_value=False):
            with pytest.raises(FileNotFoundError, match="Simulation directory not found"):
                MatlabSimulator('/invalid/path', sim_file)


class TestMatlabSimulatorOperations:
    """Tests for MatlabSimulator operations."""

    def test_start_success(self, simulator, mock_matlab_engine):
        """Test successful start of MATLAB engine."""
        simulator.start()
        assert simulator.eng is not None
        assert simulator.start_time > 0
        mock_matlab_engine.addpath.assert_called_with(
            str(Path(simulator.sim_path)), nargout=0)

    def test_start_failure(self, simulator):
        """Test failure to start MATLAB engine."""
        with patch('matlab.engine.start_matlab', side_effect=Exception("MATLAB failed")):
            with pytest.raises(MatlabSimulationError, match="Failed to start MATLAB engine"):
                simulator.start()

    def test_run_success(self, running_simulator):
        """Test successful simulation run."""
        running_simulator.eng.feval.return_value = (20.0, 30.0, 40.0)
        result = running_simulator.run(
            {'x_i': 10, 'y_i': 10, 'z_i': 10, 'v_x': 1, 'v_y': 1, 'v_z': 1, 't': 10},
            ['x_f', 'y_f', 'z_f']
        )
        assert result == {
            'x_f': approx(20.0, rel=1e-9, abs=1e-9),
            'y_f': approx(30.0, rel=1e-9, abs=1e-9),
            'z_f': approx(40.0, rel=1e-9, abs=1e-9)
        }
        running_simulator.eng.feval.assert_called_with(
            'simulation_batch', 10.0, 10.0, 10.0, 1.0, 1.0, 1.0, 10.0, nargout=3)

    def test_run_with_named_args(self, running_simulator):
        """Test simulation run with named arguments."""
        running_simulator.eng.feval.return_value = (20.0, 30.0)
        result = running_simulator.run(
            {'initial_pos': 10, 'velocity': 5},
            ['final_pos', 'final_vel']
        )
        assert result == {
            'final_pos': approx(20.0, rel=1e-9, abs=1e-9),
            'final_vel': approx(30.0, rel=1e-9, abs=1e-9)
        }
        running_simulator.eng.feval.assert_called_with(
            'simulation_batch', 10.0, 5.0, nargout=2)

    def test_run_with_empty_outputs(self, running_simulator):
        """Test simulation run with empty outputs list."""
        # The actual implementation doesn't check for empty outputs
        # This test should instead check if the return value is an empty dict
        running_simulator.eng.feval.return_value = (7.0, 8.0)
        result = running_simulator.run({'x': 10}, [])
        assert result == {
            'out0': approx(7.0, rel=1e-9, abs=1e-9),
            'out1': approx(8.0, rel=1e-9, abs=1e-9),
        }
        running_simulator.eng.feval.assert_called_with(
            'simulation_batch', 10.0, nargout=0
        )

    def test_run_without_start(self, simulator):
        """Test attempting to run without starting the engine."""
        with pytest.raises(MatlabSimulationError, match="MATLAB engine is not started"):
            simulator.run({'x': 10}, ["out1"])

    def test_run_with_matlab_error(self, running_simulator):
        """Test handling MATLAB error during run."""
        running_simulator.eng.feval.side_effect = Exception(
            "MATLAB execution error")
        with pytest.raises(MatlabSimulationError, match="Simulation error:"):
            running_simulator.run({'x': 10}, ["out1"])

    def test_close(self, running_simulator):
        """Test closing the MATLAB engine."""
        mock_eng = MagicMock()
        running_simulator.eng = mock_eng
        running_simulator.close()
        mock_eng.quit.assert_called_once()

    def test_close_without_engine(self, simulator):
        """Test closing when engine not started."""
        simulator.close()  # Should not raise any exception


class TestMatlabDataConversion:
    """Tests for data conversion between Python and MATLAB."""

    def test_to_matlab_string_conversion(self, simulator):
        """Test conversion of string Python values to MATLAB format."""
        assert simulator._to_matlab("hello") == "hello"
        assert simulator._to_matlab('') == ''

    def test_to_matlab_list_conversion(self, simulator):
        """Test conversion of list Python values to MATLAB format."""
        mock_double = Mock()
        with patch('matlab.double', return_value=mock_double) as matlab_double_mock:
            result = simulator._to_matlab([1, 2, 3])
            matlab_double_mock.assert_called_once_with([[1, 2, 3]])
            assert result == mock_double

    def test_to_matlab_nested_list_conversion(self, simulator):
        """Test conversion of nested list Python values to MATLAB format."""
        mock_double = Mock()
        with patch('matlab.double', return_value=mock_double) as matlab_double_mock:
            result = simulator._to_matlab([[1, 2], [3, 4]])
            matlab_double_mock.assert_called_once_with([[1, 2], [3, 4]])
            assert result == mock_double

    def test_from_matlab_string_conversion(self, simulator):
        """Test conversion from MATLAB string to Python."""
        assert simulator._from_matlab("hello") == "hello"
        assert simulator._from_matlab('') == ''

    def test_from_matlab_none_conversion(self, simulator):
        """Test conversion from MATLAB None to Python."""
        assert simulator._from_matlab(None) is None


class TestMatlabInputOrdering:
    """Tests for mapping dictionary inputs to MATLAB positional arguments."""

    def test_order_input_values_follows_signature(self, simulator):
        """Ensure inputs are ordered according to MATLAB signature."""
        simulator.function_inputs = ['qs', 'qg', 'tf', 'showGui', 'ts']
        inputs = {
            'qs': [1, 2],
            'qg': [3, 4],
            'showGui': True,
            'tf': 5,
            'ts': 0.01
        }
        ordered = simulator._order_input_values(inputs)
        assert ordered == [
            inputs['qs'],
            inputs['qg'],
            inputs['tf'],
            inputs['showGui'],
            inputs['ts']
        ]

    def test_order_input_values_fallback(self, simulator):
        """Fallback to dictionary ordering when signature is unavailable."""
        simulator.function_inputs = []
        inputs = {'a': 1, 'b': 2}
        assert simulator._order_input_values(inputs) == [1, 2]


class TestMatlabSimulatorMetadata:
    """Tests for MatlabSimulator metadata functionality."""

    def test_get_metadata_with_start_time(self, running_simulator):
        """Test getting metadata with start time."""
        running_simulator.start_time = 1000  # Set a specific start time

        with patch('time.time', return_value=1005), \
                patch('psutil.Process') as mock_process:
            # Set up memory_info mock
            mock_memory_info = Mock()
            mock_memory_info.rss = 150 * 1024 * 1024  # 150 MB
            mock_process.return_value.memory_info.return_value = mock_memory_info

            metadata = running_simulator.get_metadata()

        assert 'execution_time' in metadata
        assert metadata['execution_time'] == approx(5.0, rel=1e-9, abs=1e-9)

    def test_get_metadata_without_start_time(self, simulator):
        """Test getting metadata without start time."""
        with patch('psutil.Process') as mock_process:
            # Set up memory_info mock
            mock_memory_info = Mock()
            mock_memory_info.rss = 150 * 1024 * 1024  # 150 MB
            mock_process.return_value.memory_info.return_value = mock_memory_info

            metadata = simulator.get_metadata()

        assert 'memory_usage' in metadata
        assert 'execution_time' not in metadata

    def test_get_metadata_with_additional_info(self, running_simulator):
        """Test getting metadata with additional information."""
        running_simulator.start_time = 1000

        with patch('time.time', return_value=1010), \
                patch('psutil.Process') as mock_process:
            # Set up memory_info mock
            mock_memory_info = Mock()
            mock_memory_info.rss = 150 * 1024 * 1024  # 150 MB
            mock_process.return_value.memory_info.return_value = mock_memory_info

            # Mock engine eval for matlab_version
            running_simulator.eng.eval.return_value = "R2021b"

            metadata = running_simulator.get_metadata()

        assert 'execution_time' in metadata
        assert metadata['execution_time'] == approx(10.0, rel=1e-9, abs=1e-9)
        assert 'memory_usage' in metadata
        assert 'matlab_version' in metadata
        assert metadata['matlab_version'] == "R2021b"
