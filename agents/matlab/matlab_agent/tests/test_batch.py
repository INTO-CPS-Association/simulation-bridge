# tests/test_batch.py

# Import necessary libraries and modules
import time
from pathlib import Path
from unittest.mock import Mock, patch

import matlab.engine
import psutil
import pytest
from src.batch.batch import (MatlabSimulationError, MatlabSimulator,
                             handle_batch_simulation)

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

### Fixtures for filesystem ###


@pytest.fixture
def tmp_sim_dir(tmp_path):
    sim_dir = tmp_path / "sim"
    sim_dir.mkdir()
    # Crea un file vuoto simulation.m
    (sim_dir / "simulation.m").write_text("% MATLAB code")
    return sim_dir

### Validation Tests ###


def test_validate_missing_file(tmp_path):
    # directory esiste ma manca il file
    sim_dir = tmp_path / "sim2"
    sim_dir.mkdir()
    with pytest.raises(FileNotFoundError) as exc:
        MatlabSimulator(str(sim_dir), "nonexistent.m")
    assert "Simulation file 'nonexistent.m' not" in str(exc.value)

### Start / Run Tests ###


def test_run_without_start(tmp_sim_dir):
    """Chiamare run() prima di start() solleva MatlabSimulationError."""
    sim = MatlabSimulator(str(tmp_sim_dir), "simulation.m")
    with pytest.raises(MatlabSimulationError) as exc:
        sim.run({}, ["out1"])
    assert "MATLAB engine is not started" in str(exc.value)


def test_run_exception_in_feval(tmp_sim_dir):
    """Se feval solleva, viene wrapped in MatlabSimulationError."""
    sim = MatlabSimulator(str(tmp_sim_dir), "simulation.m")
    mock_eng = Mock()
    mock_eng.feval.side_effect = Exception("Feval fail")
    sim.eng = mock_eng
    with pytest.raises(MatlabSimulationError) as exc:
        sim.run({"a": 1}, ["out"])
    assert "Simulation error: Feval fail" in str(exc.value)

### _process_results Tests ###


def test_process_results_single_and_multiple(tmp_sim_dir):
    sim = MatlabSimulator(str(tmp_sim_dir), "simulation.m")
    # singolo output
    res1 = sim._process_results(matlab.double([[3.0]]), ["only"])
    assert res1 == {"only": 3.0}
    # doppio output
    tup = (matlab.double([[1.0]]), matlab.double([[2.0]]))
    res2 = sim._process_results(tup, ["x", "y"])
    assert res2 == {"x": 1.0, "y": 2.0}

### get_metadata Tests ###


def test_get_metadata_minimal(tmp_sim_dir, monkeypatch):
    """Senza start_time né eng, ritorna solo memory_usage."""
    sim = MatlabSimulator(str(tmp_sim_dir), "simulation.m")
    # forziamo un valore di RSS
    fake_info = Mock(rss=10 * 1024 * 1024)
    monkeypatch.setattr(
        psutil, "Process", lambda pid: Mock(
            memory_info=lambda: fake_info))
    meta = sim.get_metadata()
    assert "memory_usage" in meta
    assert "execution_time" not in meta
    assert "matlab_version" not in meta


def test_get_metadata_with_start_and_version(tmp_sim_dir, monkeypatch):
    """Con start_time e eng, include execution_time e matlab_version."""
    sim = MatlabSimulator(str(tmp_sim_dir), "simulation.m")
    sim.start_time = time.time() - 0.5
    mock_eng = Mock()
    mock_eng.eval.return_value = "9.12.0"
    sim.eng = mock_eng
    fake_info = Mock(rss=5 * 1024 * 1024)
    monkeypatch.setattr(
        psutil, "Process", lambda pid: Mock(
            memory_info=lambda: fake_info))
    meta = sim.get_metadata()
    assert pytest.approx(meta["execution_time"], rel=0.1) == 0.5
    assert meta["matlab_version"] == "9.12.0"
    assert meta["memory_usage"] == 5


def test_get_metadata_version_failure(tmp_sim_dir, monkeypatch):
    """Se eng.eval solleva, matlab_version non viene inserito."""
    sim = MatlabSimulator(str(tmp_sim_dir), "simulation.m")
    sim.start_time = time.time()
    mock_eng = Mock()
    mock_eng.eval.side_effect = Exception("oops")
    sim.eng = mock_eng
    fake_info = Mock(rss=1 * 1024 * 1024)
    monkeypatch.setattr(
        psutil, "Process", lambda pid: Mock(
            memory_info=lambda: fake_info))
    meta = sim.get_metadata()
    assert "matlab_version" not in meta

### _to_matlab / _from_matlab Tests ###


def test_to_matlab_empty_and_numeric(tmp_sim_dir):
    sim = MatlabSimulator(str(tmp_sim_dir), "simulation.m")
    # lista vuota
    empty = sim._to_matlab([])
    assert isinstance(empty, matlab.double)
    # numero intero e float
    assert sim._to_matlab(5) == 5.0
    assert sim._to_matlab(3.14) == 3.14
    # tuple
    dbl = sim._to_matlab((1, 2, 3))
    assert isinstance(dbl, matlab.double)


def test_to_matlab_other_types(tmp_sim_dir):
    sim = MatlabSimulator(str(tmp_sim_dir), "simulation.m")
    # stringa passa inalterata
    assert sim._to_matlab("hello") == "hello"


def test_from_matlab_various_shapes(tmp_sim_dir):
    sim = MatlabSimulator(str(tmp_sim_dir), "simulation.m")
    # scala 1x1
    one = matlab.double([[7.0]])
    assert sim._from_matlab(one) == 7.0
    # vettore riga
    row = matlab.double([[1.0, 2.0, 3.0]])
    assert sim._from_matlab(row) == [1.0, 2.0, 3.0]
    # vettore colonna
    col = matlab.double([[4.0], [5.0], [6.0]])
    assert sim._from_matlab(col) == [4.0, 5.0, 6.0]
    # matrice 2x2
    mat2 = matlab.double([[1.0, 2.0], [3.0, 4.0]])
    assert sim._from_matlab(mat2) == [[1.0, 2.0], [3.0, 4.0]]

### close() Warning Branch ###


def test_close_with_quit_error(tmp_sim_dir, caplog):
    sim = MatlabSimulator(str(tmp_sim_dir), "simulation.m")
    mock_eng = Mock()
    mock_eng.quit.side_effect = Exception("quit failed")
    sim.eng = mock_eng
    caplog.set_level("WARNING")
    sim.close()
    # non deve sollevare, ma loggare warning
    assert "Error closing MATLAB engine: quit failed" in caplog.text
    assert sim.eng is None
