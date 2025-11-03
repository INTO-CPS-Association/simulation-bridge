"""Unit tests for the batch processing module with improved structure."""

from pathlib import Path


from unittest.mock import Mock, patch, call, ANY, MagicMock
import pytest
from src.core.simul8_simulator import Simul8SimulationError
from src.core.batch import (
    handle_batch_simulation,
    _validate_simulation_data,
    _extract_io_specs,
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
        'simulation': {'path': 'simul8_agent/docs/examples'},
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
        path_simulation = 'simul8_agent/docs/examples'

        with patch('pathlib.Path.is_file', return_value=True):
            sim_file = _validate_simulation_data(data, path_simulation)
            assert sim_file == 'simulation_batch.s8'

    def test_missing_file_key(self):
        """Test validation fails when 'file' key is missing."""
        data = {}
        path_simulation = 'simul8_agent/docs/examples'

        with pytest.raises(ValueError, match="Missing 'file' in simulation config"):
            _validate_simulation_data(data, path_simulation)

    def test_empty_file_value(self):
        """Test validation fails when 'file' value is empty."""
        data = {'file': ''}
        path_simulation = 'simul8_agent/docs/examples'

        with pytest.raises(ValueError, match="Missing 'file' in simulation config"):
            _validate_simulation_data(data, path_simulation)

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

    def test_file_path_construction(self):
        """Test that file path is constructed correctly."""
        data = {'file': 'simulation_batch.s8'}
        path_simulation = 'simul8_agent/docs/examples'

        with patch('pathlib.Path.is_file', return_value=True) as mock_is_file:
            _validate_simulation_data(data, path_simulation)
            # Verify the path was checked correctly
            expected_path = Path(path_simulation) / 'simulation_batch.s8'
            mock_is_file.assert_called_once()


class TestExtractIOSpecs:
    """Tests for _extract_io_specs function."""

    def test_valid_io_specs(self):
        """Test extraction with valid IO specs."""
        data = {
            'inputs': {'run_time': 500, 'columns': ['co2', 'energy']},
            'outputs': ['total_co2', 'total_energy']
        }
        inputs, outputs, run_time = _extract_io_specs(data)
        assert inputs == {'columns': ['co2', 'energy']}
        assert outputs == ['total_co2', 'total_energy']
        assert run_time == 500

    def test_missing_outputs(self):
        """Test extraction with missing outputs."""
        with pytest.raises(ValueError, match="No outputs specified"):
            _extract_io_specs({'inputs': {'run_time': 500}})

    def test_empty_inputs(self):
        """Test extraction with empty inputs."""
        data = {'outputs': ['total_co2']}
        inputs, outputs, run_time = _extract_io_specs(data)
        assert inputs == {}
        assert outputs == ['total_co2']
        assert run_time == 500


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

        _send_response(broker_mock, 'test_queue', response)

        broker_mock.send_result.assert_called_once_with('test_queue', response)


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


class TestDetermineErrorType:
    """Tests for _determine_error_type function."""

    def test_file_not_found_error(self):
        """Test determining FileNotFoundError type."""
        assert _determine_error_type(FileNotFoundError()) == 'missing_file'

    def test_simul8_simulation_error_com_cache(self):
        """Test determining Simul8SimulationError type for COM cache error."""
        error = Simul8SimulationError("Error related to clsidtoclassmap")
        assert _determine_error_type(error) == 'com_cache_error'

    def test_timeout_error(self):
        """Test determining TimeoutError type."""
        assert _determine_error_type(TimeoutError()) == 'timeout'

    def test_value_error(self):
        """Test determining ValueError type."""
        assert _determine_error_type(ValueError()) == 'invalid_config'

    def test_unknown_error(self):
        """Test determining unknown error type."""
        assert _determine_error_type(Exception()) == 'execution_error'


class TestHandleBatchSimulation:
    """Tests for handle_batch_simulation function (Simul8-specific)."""

    @pytest.fixture
    def sim_data(self):
        """Provide standard simulation data."""
        return {
            'simulation': {
                'name': 'test_sim',
                'file': 'simulation_batch.s8',
                'inputs': {
                    'columns': ['co2', 'energy'],
                    'r1': ['25', '100'],
                    'r2': ['25', '200']
                },
                'outputs': {
                    'total_co2': 'Total CO2',
                    'total_energy': 'Total Energy'
                },
                'bridge_meta': 'test_bridge',
                'request_id': 'test_request_id'
            }
        }

    @pytest.fixture
    def broker_mock(self):
        """Provide a mock broker."""
        mock = MagicMock()
        mock.send_result = MagicMock()
        return mock

    @pytest.fixture
    def templates(self):
        """Provide standard templates."""
        return {
            'success': {'include_metadata': True},
            'progress': {'include_percentage': True},
            'error': {'include_stacktrace': False}
        }

    def test_validation_error_missing_file(self, broker_mock, templates):
        """Test handling of validation errors (missing file)."""
        sim_data = {
            'simulation': {
                'name': 'test_sim',
                'bridge_meta': 'test_bridge',
                'request_id': 'test_request_id'
            }
        }

        with patch('src.core.batch._handle_error') as handle_error_mock:
            handle_batch_simulation(
                sim_data,
                'test_queue',
                broker_mock,
                'test/path',
                templates
            )

            # Verify error handler was called
            handle_error_mock.assert_called_once()

            # Check the error argument
            error = handle_error_mock.call_args[0][0]
            assert isinstance(error, ValueError)
            assert "Missing 'file'" in str(
                error) or "file" in str(error).lower()

    def test_run_error(self, sim_data, broker_mock, templates):
        """Test handling of simulation execution errors."""
        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.is_file', return_value=True), \
                patch('pathlib.Path.is_dir', return_value=True), \
                patch('src.core.batch.Simul8Simulator') as sim_mock, \
                patch('src.core.batch._handle_error') as handle_error_mock, \
                patch('src.core.batch._send_progress'):

            # Setup simulator to raise error
            simulator_instance = MagicMock()
            simulator_instance.run.side_effect = Simul8SimulationError(
                "Simulation execution failed")
            sim_mock.return_value = simulator_instance

            handle_batch_simulation(
                sim_data,
                'test_queue',
                broker_mock,
                'test/path',
                templates
            )

            # Verify error handler was called
            handle_error_mock.assert_called_once()

            # Check the error
            error = handle_error_mock.call_args[0][0]
            assert isinstance(error, Simul8SimulationError)
            assert "Simulation execution failed" in str(error)

            # Verify cleanup was still called
            simulator_instance.cleanup.assert_called_once()
