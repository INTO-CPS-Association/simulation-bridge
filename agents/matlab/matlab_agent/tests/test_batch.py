"""Unit tests for the batch processing module with improved structure."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from unittest.mock import MagicMock

import matlab.engine
from src.batch.batch import MatlabSimulationError, MatlabSimulator, handle_batch_simulation


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
def patch_path_exists(monkeypatch):
    """Patch Path.exists to return True."""
    def mock_exists(*args, **kwargs):
        return True

    monkeypatch.setattr(Path, "exists", mock_exists)


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


@pytest.fixture
def sample_simulation_data():
    """Provide sample simulation data for tests."""
    return {
        'simulation': {
            'name': 'test_sim',
            'path': 'matlab_agent/docs/examples',
            'file': 'simulation_batch.m',
            'inputs': {'param1': 10, 'x_i': 10, 'y_i': 10, 'z_i': 10,
                       'v_x': 1, 'v_y': 1, 'v_z': 1, 't': 10},
            'outputs': ['result1', 'x_f', 'y_f', 'z_f']
        }
    }


@pytest.fixture
def mock_rabbitmq():
    """Provide a mock RabbitMQ client."""
    return Mock()


class TestMatlabSimulatorInitialization:
    """Tests for MatlabSimulator initialization."""

    def test_init_with_valid_path(self, simulator, sim_path, sim_file):
        """Test initialization with a valid path."""
        assert simulator.sim_path == Path(sim_path).resolve()
        assert simulator.function_name == "simulation_batch"

    def test_init_with_invalid_path(self, sim_file):
        """Test initialization with an invalid path raises FileNotFoundError."""
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = False
            with pytest.raises(FileNotFoundError):
                MatlabSimulator('/invalid/path', sim_file)


class TestMatlabSimulatorOperations:
    """Tests for MatlabSimulator operations."""

    def test_start_success(self, simulator, mock_matlab_engine):
        simulator.start()
        mock_matlab_engine.addpath.assert_called_with(
            str(Path(simulator.sim_path)), nargout=0)

    def test_start_failure(self, simulator):
        with patch('matlab.engine.start_matlab') as mock_start:
            mock_start.side_effect = Exception("MATLAB failed")
            with pytest.raises(MatlabSimulationError):
                simulator.start()

    def test_run_success(self, running_simulator):
        running_simulator.eng.feval.return_value = (20.0, 20.0, 20.0)
        result = running_simulator.run(
            {'x_i': 10, 'y_i': 10, 'z_i': 10, 'v_x': 1, 'v_y': 1, 'v_z': 1, 't': 10},
            ['x_f', 'y_f', 'z_f']
        )
        assert result == {'x_f': 20.0, 'y_f': 20.0, 'z_f': 20.0}
        running_simulator.eng.feval.assert_called_with(
            'simulation_batch', 10.0, 10.0, 10.0, 1.0, 1.0, 1.0, 10.0, nargout=3)

    def test_run_without_start(self, simulator):
        with pytest.raises(MatlabSimulationError) as exc:
            simulator.run({}, ["out1"])
        assert "MATLAB engine is not started" in str(exc.value)

    def test_close(self, running_simulator):
        mock_eng = MagicMock()
        running_simulator.eng = mock_eng
        running_simulator.close()
        mock_eng.quit.assert_called_once()


class TestMatlabDataConversion:
    """Tests for data conversion between Python and MATLAB."""

    def test_matlab_to_python_conversion(self, simulator):
        """Test conversion from MATLAB to Python datatypes."""
        # Test scalar conversion
        assert simulator._from_matlab(matlab.double([[5.0]])) == 5.0

        # Test vector conversion
        py_row = [1.0, 2.0, 3.0]
        matlab_row = matlab.double([py_row])
        assert simulator._from_matlab(matlab_row) == py_row

        # Test 2D array conversion
        py_matrix = [[1.0, 2.0], [3.0, 4.0]]
        matlab_matrix = matlab.double(py_matrix)
        assert simulator._from_matlab(matlab_matrix) == py_matrix

    def test_python_to_matlab_conversion(self, simulator):
        """Test conversion from Python to MATLAB datatypes."""
        # Test numeric conversion
        assert simulator._to_matlab(5) == 5.0
        assert simulator._to_matlab(3.14) == 3.14

        # Test list conversion
        py_list = [1, 2, 3]
        matlab_list = simulator._to_matlab(py_list)
        assert isinstance(matlab_list, matlab.double)

        # Test string handling
        assert simulator._to_matlab("hello") == "hello"


@patch('src.batch.batch.MatlabSimulator')
class TestBatchHandling:
    """Tests for the batch simulation handling functionality."""

    def test_batch_success(
            self,
            MockSimulator,
            mock_rabbitmq,
            sample_simulation_data):
        mock_instance = Mock()
        mock_instance.run.return_value = {
            'result1': 42, 'x_f': 20.0, 'y_f': 20.0, 'z_f': 20.0}
        mock_instance.get_metadata.return_value = {'exec_time': 1.0}
        MockSimulator.return_value = mock_instance

        handle_batch_simulation(
            sample_simulation_data,
            'test_queue',
            mock_rabbitmq
        )

        # Since the handler sends progress twice + final result, expect 3 calls
        assert mock_rabbitmq.send_result.call_count == 3

        # The last call must have status 'completed' with outputs
        last_call_args = mock_rabbitmq.send_result.call_args_list[-1][0]
        assert last_call_args[0] == 'test_queue'  # queue name
        response = last_call_args[1]
        assert response['status'] == 'completed'
        assert response['simulation']['outputs']['result1'] == 42

    def test_batch_matlab_error(
            self,
            MockSimulator,
            mock_rabbitmq,
            sample_simulation_data):
        mock_instance = Mock()
        mock_instance.start.side_effect = MatlabSimulationError("Start failed")
        MockSimulator.return_value = mock_instance

        handle_batch_simulation(
            sample_simulation_data,
            'test_queue',
            mock_rabbitmq
        )

        # The last sent response must be an error
        last_call_args = mock_rabbitmq.send_result.call_args_list[-1][0]
        response = last_call_args[1]
        assert response['status'] == 'error'
        assert 'error' in response
        # Adjust this according to your create_response error fields if needed
        # For example, if you include a code field:
        # assert response['error']['code'] == 500

    def test_batch_missing_fields(self, MockSimulator, mock_rabbitmq):
        invalid_data = {'simulation': {'name': 'test'}}

        handle_batch_simulation(
            invalid_data,
            'test_queue',
            mock_rabbitmq
        )

        last_call_args = mock_rabbitmq.send_result.call_args_list[-1][0]
        response = last_call_args[1]
        assert response['status'] == 'error'
        # Usually a ValueError triggers invalid_config type error
        # You may add checks on error type/message if create_response provides
        # it
