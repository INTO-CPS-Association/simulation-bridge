"""Unit tests for the batch processing module with improved structure."""

from unittest.mock import Mock, patch, call, ANY

import pytest

from src.core.simul8_simulator import Simul8SimulationError
from src.core.batch import (
    handle_batch_simulation,
    _validate_simulation_data,
    _extract_io_specs,
    _handle_simulation,
    _send_progress,
    _get_metadata,
    _send_response,
    _handle_error,
    _determine_error_type
)


@pytest.fixture
def config_mock():
    """Mock for the configuration."""
    return {
        'simulation': {'path': 'simul8/docs/examples'},
        'response_templates': {
            'success': {'include_metadata': True},
            'progress': {'include_percentage': True},
            'error': {'include_stacktrace': False}
        }
    }


@pytest.fixture
def patched_config(monkeypatch, config_mock):  # pylint: disable=unused-argument
    """Patch the configuration loader to return our mock config."""
    with patch('src.core.batch.config', config_mock):
        yield config_mock


@pytest.fixture
def sim_path():
    """Provide a standard simulation path."""
    return "simul8_agent/docs/examples"


@pytest.fixture
def sim_file():
    """Provide a standard simulation file name."""
    return "simulation_batch.m"


@pytest.fixture
def simul8_simulator_mock():
    """Provide a mock for the Simul8Simulator class."""
    with patch('src.core.batch.Simul8Simulator') as mock:
        simulator_instance = Mock()
        simulator_instance.run.return_value = {
            'x_f': 20.0, 'y_f': 20.0, 'z_f': 20.0}
        simulator_instance.get_metadata.return_value = {'exec_time': 1.0}
        mock.return_value = simulator_instance
        yield mock, simulator_instance


@pytest.fixture
def message_broker_mock():
    """Provide a mock for the message broker."""
    broker = Mock()
    broker.send_result = Mock()
    return broker


@pytest.fixture
def sample_simulation_data():
    """Provide sample simulation data for tests."""
    return {
        'simulation': {
            'name': 'test_sim',
            'file': 'simulation_batch.s8',
            'inputs': { 
                'run_time': 500,
                'columns': ['co2', 'energy'],
                'r1': [25, 100],
                'r2': [25, 200]
            },
            'outputs': ['total_co2', 'total_energy']
        }
    }


@pytest.fixture
def create_response_mock():
    """Mock the create_response function."""
    with patch('src.core.batch.create_response') as mock:
        mock.return_value = {'status': 'mocked_response'}
        yield mock


@pytest.fixture
def response_templates():
    """Fixture providing standardized response templates for tests."""
    return {
        'success': {'include_metadata': True},
        'progress': {'include_percentage': True},
        'error': {'include_stacktrace': False}
    }


class TestValidateSimulationData:
    """Tests for _validate_simulation_data function."""

    def test_valid_data(self):
        """Test validation with valid data."""
        data = {'file': 'simulation_batch.s8'}
        sim_file = _validate_simulation_data(data)
        assert sim_file == 'simulation_batch.s8'

    def test_missing_file(self):
        """Test validation with missing file."""
        with pytest.raises(ValueError, match="Missing 'file'"):
            _validate_simulation_data({})


class TestExtractIOSpecs:
    """Tests for _extract_io_specs function."""

    def test_valid_io_specs(self):
        """Test extraction with valid IO specs."""
        data = {
            'inputs': {'run_time': 500, 'columns': ['co2', 'energy']},
            'outputs': ['total_co2', 'total_energy']
        }
        inputs, outputs = _extract_io_specs(data)
        assert inputs == {'columns': ['co2', 'energy']}
        assert outputs == ['total_co2', 'total_energy']

    def test_missing_outputs(self):
        """Test extraction with missing outputs."""
        with pytest.raises(ValueError, match="No outputs specified"):
            _extract_io_specs({'inputs': {'run_time': 500}})

    def test_empty_inputs(self):
        """Test extraction with empty inputs."""
        data = {'outputs': ['total_co2']}
        inputs, outputs = _extract_io_specs(data)
        assert inputs == {}
        assert outputs == ['total_co2']

class TestSendProgress:
    """Tests for _send_progress function."""

    def test_send_progress_enabled(self):
        """Test sending progress when enabled."""
        broker_mock = Mock()
        broker_mock.send_result = Mock()
        templates = {
            'progress': {'include_percentage': True}
        }
        with patch('src.core.batch.create_response') as response_mock:
            response_mock.return_value = {'status': 'mocked_response'}
            _send_progress(broker_mock, 'test_queue', 'sim.s8', 50, templates)
            response_mock.assert_called_once_with(
                'progress', 'sim.s8', 'batch', templates, percentage=50,
                bridge_meta='unknown', request_id='unknown')
            broker_mock.send_result.assert_called_once()

    def test_send_progress_disabled(self):
        """Test not sending progress when disabled."""
        broker_mock = Mock()
        broker_mock.send_result = Mock()
        templates = {
            'progress': {'include_percentage': False}
        }
        with patch('src.core.batch.create_response') as response_mock:
            _send_progress(broker_mock, 'test_queue', 'sim.m', 50, templates)
            response_mock.assert_not_called()
            broker_mock.send_result.assert_not_called()


class TestGetMetadata:
    """Tests for _get_metadata function."""

    def test_get_metadata(self):
        """Test retrieving metadata from simulator."""
        sim = Mock()
        sim.get_metadata.return_value = {
            'exec_time': 1.5, 'memory_usage': '256MB'}

        result = _get_metadata(sim)

        assert result == {'exec_time': 1.5, 'memory_usage': '256MB'}
        sim.get_metadata.assert_called_once()


class TestSendResponse:
    """Tests for _send_response function."""

    def test_send_response(self):
        """Test sending response via broker."""
        broker_mock = Mock()
        broker_mock.send_result = Mock()
        response = {'status': 'completed', 'data': {'result': 42}}

        with patch('src.core.batch.yaml.dump') as mock_dump, \
                patch('src.core.batch.logger.debug') as mock_logger_debug:

            _send_response(broker_mock, 'test_queue', response)

        broker_mock.send_result.assert_called_once_with('test_queue', response)
        mock_dump.assert_called_once_with(response)
        mock_logger_debug.assert_called_once_with(mock_dump.return_value)


class TestHandleError:
    """Tests for _handle_error function."""

    def test_handle_file_not_found_error(self):
        """Test handling FileNotFoundError."""
        broker_mock = Mock()
        broker_mock.send_result = Mock()
        templates = {'error': {'include_stacktrace': False}}
        error = FileNotFoundError("File not found")

        with patch('src.core.batch._determine_error_type', return_value='missing_file') as mock_determine, \
                patch('src.core.batch.create_response', return_value={'status': 'error'}) as response_mock, \
                patch('src.core.batch._send_response') as send_response_mock:

            _handle_error(error, 'sim.m', broker_mock, 'test_queue', templates)

        mock_determine.assert_called_once_with(error)
        response_mock.assert_called_once()
        send_response_mock.assert_called_once_with(
            broker_mock, 'test_queue', {'status': 'error'})

    def test_handle_value_error(self):
        """Test handling ValueError."""
        broker_mock = Mock()
        broker_mock.send_result = Mock()
        templates = {'error': {'include_stacktrace': False}}
        error = ValueError("Invalid config")

        with patch('src.core.batch._determine_error_type', return_value='invalid_config') as mock_determine, \
                patch('src.core.batch.create_response', return_value={'status': 'error'}) as response_mock, \
                patch('src.core.batch._send_response') as send_response_mock:

            _handle_error(error, 'sim.m', broker_mock, 'test_queue', templates)

        mock_determine.assert_called_once_with(error)
        response_mock.assert_called_once()
        send_response_mock.assert_called_once_with(
            broker_mock, 'test_queue', {'status': 'error'})


# class TestDetermineErrorType: #TODO
#     """Tests for _determine_error_type function."""

#     def test_file_not_found_error(self):
#         """Test determining FileNotFoundError type."""
#         raise NotImplementedError("FileNotFoundError test not implemented")

class TestHandleBatchSimulation:
    """Tests for handle_batch_simulation function."""

    def test_successful_simulation(self):
        """Test successful simulation execution."""
        sim_data = {
            'simulation': {
            'name': 'test_sim',
            'file': 'simulation_batch.s8',
            'inputs': { 
                'run_time': 500,
                'columns': ['co2', 'energy'],
                'r1': [25, 100],
                'r2': [25, 200]
            },
            'outputs': ['total_co2', 'total_energy'],
                'bridge_meta': 'test_bridge',
                'request_id': 'test_request_id'
            }
        }
        broker_mock = Mock()
        broker_mock.send_result = Mock()
        templates = {
            'success': {'include_metadata': True},
            'progress': {'include_percentage': True},
            'error': {'include_stacktrace': False}
        }
        with patch('src.core.batch.Simul8Simulator') as sim_mock, \
                patch('src.core.batch.create_response') as response_mock, \
                patch('src.core.batch._send_progress') as progress_mock:
            simulator_instance = Mock()
            simulator_instance.run.return_value = {
                'x_f': 20.0, 'y_f': 20.0, 'z_f': 20.0}
            simulator_instance.get_metadata.return_value = {'exec_time': 1.0}
            sim_mock.return_value = simulator_instance
            response_mock.return_value = {'status': 'success'}
            handle_batch_simulation(
                sim_data,
                'test_queue',
                broker_mock,
                'test/path',
                templates)
            sim_mock.assert_called_once_with(
                'test/path',
                sim_data['simulation']['file'],
                
            )
            progress_calls = [
                call(broker_mock, 'test_queue', sim_data['simulation']['file'], 0,
                     templates, 'test_bridge', 'test_request_id'),
                call(broker_mock, 'test_queue', sim_data['simulation']['file'], 50,
                     templates, 'test_bridge', 'test_request_id')
            ]
            assert progress_mock.call_count == 2
            progress_mock.assert_has_calls(progress_calls)
            simulator_instance.start.assert_called_once()
            simulator_instance.run.assert_called_once_with(
                sim_data['simulation']['inputs'],
                sim_data['simulation']['outputs']
            )
            response_mock.assert_called_with(
                'success',
                sim_data['simulation']['file'],
                'batch',
                templates,
                outputs=simulator_instance.run.return_value,
                metadata=simulator_instance.get_metadata.return_value,
                bridge_meta='test_bridge',
                request_id='test_request_id'
            )
            broker_mock.send_result.assert_called_with(
                'test_queue', response_mock.return_value)
            simulator_instance.close.assert_called_once()

    def test_validation_error(self):
        """Test handling of validation errors."""
        sim_data = {
            'simulation': {
                'name': 'test_sim',
                'bridge_meta': 'test_bridge'
            }
        }
        broker_mock = Mock()
        templates = {'error': {'include_stacktrace': False}}
        with patch('src.core.batch._handle_error') as handle_error_mock:
            handle_batch_simulation(
                sim_data,
                'test_queue',
                broker_mock,
                'test/path',
                templates)
            handle_error_mock.assert_called_once_with(
                ANY,  # error
                None,  # sim_file
                broker_mock,
                'test_queue',
                templates
            )
            error = handle_error_mock.call_args[0][0]
            assert isinstance(error, ValueError)
            assert str(error) == "Missing 'file' in simulation config"

    # def test_matlab_error(self): #TODO
    #     """Test handling of MATLAB startup errors."""
    #     sim_data = {
    #         'simulation': {
    #             'name': 'test_sim',
    #             'file': 'simulation_batch.m',
    #             'function_name': 'simulation_batch',
    #             'inputs': {'param1': 10},
    #             'outputs': ['result1'],
    #             'bridge_meta': 'test_bridge'
    #         }
    #     }
    #     broker_mock = Mock()
    #     templates = {'error': {'include_stacktrace': False}}
    #     with patch('src.core.batch.Simul8Simulator') as sim_mock, \
    #             patch('src.core.batch._handle_error') as handle_error_mock:
    #         simulator_instance = Mock()
    #         simulator_instance.start.side_effect = Simul8SimulationError(
    #             "Simul8 engine failed to start")
    #         sim_mock.return_value = simulator_instance
    #         handle_batch_simulation(
    #             sim_data,
    #             'test_queue',
    #             broker_mock,
    #             'test/path',
    #             templates)
    #         handle_error_mock.assert_called_once_with(
    #             ANY,  # error
    #             sim_data['simulation']['file'],
    #             broker_mock,
    #             'test_queue',
    #             templates
    #         )
    #         error = handle_error_mock.call_args[0][0]
    #         assert isinstance(error, Simul8SimulationError)
    #         assert str(error) == "Simul8 engine failed to start"
    #         simulator_instance.close.assert_called_once()

    def test_run_error(self):
        """Test handling of simulation execution errors."""
        sim_data = {
            'simulation': {
                'name': 'test_sim',
                'file': 'simulation_batch.m',
                'inputs': {'param1': 10},
                'outputs': ['result1'],
                'bridge_meta': 'test_bridge'
            }
        }
        broker_mock = Mock()
        templates = {'error': {'include_stacktrace': False}}
        with patch('src.core.batch.Simul8Simulator') as sim_mock, \
                patch('src.core.batch._handle_error') as handle_error_mock:
            simulator_instance = Mock()
            simulator_instance.run.side_effect = Simul8SimulationError(
                "Simulation execution failed")
            sim_mock.return_value = simulator_instance
            handle_batch_simulation(
                sim_data,
                'test_queue',
                broker_mock,
                'test/path',
                templates)
            handle_error_mock.assert_called_once_with(
                ANY,  # error
                sim_data['simulation']['file'],
                broker_mock,
                'test_queue',
                templates
            )
            error = handle_error_mock.call_args[0][0]
            assert isinstance(error, Simul8SimulationError)
            assert str(error) == "Simulation execution failed"
            simulator_instance.close.assert_called_once()
