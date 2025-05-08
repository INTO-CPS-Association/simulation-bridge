# tests/test_batch.py

# Import necessary libraries and modules
import pytest
from unittest.mock import Mock, patch, MagicMock, call
import matlab.engine
import sys
import traceback
from pathlib import Path
from datetime import datetime
from src.batch.batch import (
    MatlabSimulator,
    create_response,
    handle_batch_simulation,
    MatlabSimulationError
)

### Fixtures ###

# Mock configuration fixture


@pytest.fixture
def mock_config():
    return {
        'response_templates': {
            'success': {
                'status': 'completed',
                'include_metadata': True,
                'timestamp_format': '%Y-%m-%dT%H:%M:%SZ'
            },
            'error': {
                'status': 'error',
                'error_codes': {
                    'invalid_config': 400,
                    'matlab_start_failure': 500
                },
                'include_stacktrace': False
            },
            'progress': {
                'status': 'in_progress',
                'include_percentage': True
            }
        }
    }

# Mock RabbitMQ fixture


@pytest.fixture
def mock_rabbitmq():
    return Mock()

# Sample simulation data fixture


@pytest.fixture
def sample_sim_data():
    return {
        'simulation': {
            'name': 'test_sim',
            'path': 'matlab_agent/docs/examples',
            'file': 'simulation_batch.m',
            'inputs': {'param1': 10},
            'outputs': ['result1']
        }
    }

### MatlabSimulator Tests ###

# Test MatlabSimulator initialization with a valid path


def test_matlab_simulator_init_valid(mock_config):
    with patch('pathlib.Path.exists') as mock_exists:
        mock_exists.return_value = True
        simulator = MatlabSimulator(
            'matlab_agent/docs/examples', 'simulation_batch.m')
        assert simulator.sim_path == Path(
            'matlab_agent/docs/examples').resolve()
        assert simulator.function_name == 'simulation_batch'

# Test MatlabSimulator initialization with an invalid path


def test_matlab_simulator_init_invalid_path():
    with patch('pathlib.Path.exists') as mock_exists:
        mock_exists.return_value = False
        with pytest.raises(FileNotFoundError):
            MatlabSimulator('/invalid/path', 'simulation_batch.m')

# Test successful MATLAB engine start


@patch('matlab.engine.start_matlab')
def test_matlab_simulator_start_success(mock_start, mock_config):
    mock_engine = Mock()
    mock_start.return_value = mock_engine

    simulator = MatlabSimulator(
        'matlab_agent/docs/examples', 'simulation_batch.m')
    simulator.start()

    mock_start.assert_called_once()
    mock_engine.addpath.assert_called_with(
        str(Path('matlab_agent/docs/examples').resolve()), nargout=0)

# Test MATLAB engine start failure


@patch('matlab.engine.start_matlab')
def test_matlab_simulator_start_failure(mock_start):
    mock_start.side_effect = Exception("MATLAB failed")
    simulator = MatlabSimulator(
        'matlab_agent/docs/examples', 'simulation_batch.m')
    with pytest.raises(MatlabSimulationError):
        simulator.start()

# Test successful simulation run


def test_matlab_simulator_run_success():
    mock_engine = Mock()
    mock_engine.feval.return_value = (20.0, 20.0, 20.0)  # Simulated output

    simulator = MatlabSimulator(
        'matlab_agent/docs/examples', 'simulation_batch.m')
    simulator.eng = mock_engine

    result = simulator.run({'x_i': 10, 'y_i': 10, 'z_i': 10, 'v_x': 1,
                           'v_y': 1, 'v_z': 1, 't': 10}, ['x_f', 'y_f', 'z_f'])

    assert result == {'x_f': 20.0, 'y_f': 20.0, 'z_f': 20.0}
    mock_engine.feval.assert_called_with(
        'simulation_batch', 10.0, 10.0, 10.0, 1.0, 1.0, 1.0, 10.0, nargout=3)

# Test type conversion between Python and MATLAB


def test_matlab_simulator_type_conversion():
    simulator = MatlabSimulator(
        'matlab_agent/docs/examples', 'simulation_batch.m')

    # Python to MATLAB
    assert isinstance(simulator._to_matlab([1, 2, 3]), matlab.double)

    # MATLAB to Python
    matlab_double = matlab.double([[1.0, 2.0], [3.0, 4.0]])
    assert simulator._from_matlab(matlab_double) == [[1.0, 2.0], [3.0, 4.0]]

# Test MATLAB engine closure


def test_matlab_simulator_close():
    mock_engine = Mock()
    simulator = MatlabSimulator(
        'matlab_agent/docs/examples', 'simulation_batch.m')
    simulator.eng = mock_engine
    simulator.close()
    mock_engine.quit.assert_called_once()


### Batch Handler Tests ###

# Test successful batch simulation handling
@patch('src.batch.batch.MatlabSimulator')
def test_handle_batch_success(MockSim, mock_rabbitmq, sample_sim_data):
    mock_instance = Mock()
    mock_instance.run.return_value = {'result1': 42}
    mock_instance.get_metadata.return_value = {'exec_time': 1.0}
    MockSim.return_value = mock_instance

    handle_batch_simulation(
        {'simulation': sample_sim_data['simulation']},
        'test_queue',
        mock_rabbitmq
    )

    sent_response = mock_rabbitmq.send_result.call_args[0][1]
    assert sent_response['status'] == 'completed'
    assert sent_response['simulation']['outputs']['result1'] == 42

# Test batch simulation handling with MATLAB error


@patch('src.batch.batch.MatlabSimulator')
def test_handle_batch_matlab_error(MockSim, mock_rabbitmq, sample_sim_data):
    mock_instance = Mock()
    mock_instance.start.side_effect = MatlabSimulationError("Start failed")
    MockSim.return_value = mock_instance

    handle_batch_simulation(
        {'simulation': sample_sim_data['simulation']},
        'test_queue',
        mock_rabbitmq
    )

    sent_response = mock_rabbitmq.send_result.call_args[0][1]
    assert sent_response['status'] == 'error'
    assert sent_response['error']['code'] == 500

# Test batch simulation handling with missing fields


def test_handle_batch_missing_fields(mock_rabbitmq):
    invalid_data = {'simulation': {'name': 'test'}}

    handle_batch_simulation(
        invalid_data,
        'test_queue',
        mock_rabbitmq
    )

    sent_response = mock_rabbitmq.send_result.call_args[0][1]
    assert sent_response['error']['code'] == 400

### Error Handling Tests ###

# Test error wrapping for MATLAB simulation errors


def test_simulation_error_wrapping():
    with patch('matlab.engine.start_matlab') as mock_start:
        mock_start.side_effect = Exception("MATLAB crash")
        with pytest.raises(MatlabSimulationError):
            simulator = MatlabSimulator(
                'matlab_agent/docs/examples', 'simulation_batch.m')
            simulator.start()


# Test complex type conversions between Python and MATLAB
def test_complex_type_conversions():
    simulator = MatlabSimulator(
        'matlab_agent/docs/examples', 'simulation_batch.m')

    # Test 2D array conversion
    py_array = [[1, 2], [3, 4]]
    matlab_array = simulator._to_matlab(py_array)
    converted_back = simulator._from_matlab(matlab_array)
    assert converted_back == py_array

    # Test single value conversion
    assert simulator._from_matlab(matlab.double([[5.0]])) == 5.0
