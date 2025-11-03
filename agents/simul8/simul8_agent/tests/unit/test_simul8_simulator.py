"""Unit tests for the Simul8 simulator module."""
from unittest.mock import patch, MagicMock, mock_open, call
from pathlib import Path
from src.core.simul8_simulator import Simul8Simulator, Simul8SimulationError
from src.utils.csv_parser import CSVFormatError
import psutil
import pytest


@pytest.fixture(name="sim_path")
def _sim_path_fixture():
    """Provide a standard simulation path."""
    return "simul8_agent/docs/examples"


@pytest.fixture(name="sim_file")
def _sim_file_fixture():
    """Provide a standard simulation file name."""
    return "simulation_batch.s8"


@pytest.fixture(name="simulator")
def _simulator_fixture(sim_path, sim_file):
    """Create a Simul8Simulator instance with mocked dependencies."""
    with patch('pathlib.Path.exists', return_value=True), \
            patch('pathlib.Path.is_dir', return_value=True), \
            patch('pathlib.Path.is_file', return_value=True):
        return Simul8Simulator(sim_path, sim_file)


@pytest.fixture(name="valid_inputs")
def _valid_inputs_fixture():
    """Provide valid input structure."""
    return {
        'columns': ['energy', 'co2'],
        'r1': ['100', '50'],
        'r2': ['200', '75']
    }


@pytest.fixture(name="valid_outputs")
def _valid_outputs_fixture():
    """Provide valid output structure."""
    return {
        'total_co2': 'Total CO2',
        'total_energy': 'Total Energy'
    }

# pylint: disable=protected-access


class TestSimul8SimulatorInitialization:
    """Tests for Simul8Simulator initialization."""

    def test_init_with_valid_path(self, sim_path, sim_file):
        """Test initialization with a valid path."""
        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.is_dir', return_value=True), \
                patch('pathlib.Path.is_file', return_value=True):
            simulator = Simul8Simulator(sim_path, sim_file)
            assert simulator.sim_path == Path(sim_path).resolve()
            assert simulator.sim_file == sim_file

    def test_init_with_invalid_path(self, sim_file):
        """Test initialization with an invalid path raises FileNotFoundError."""
        with patch('pathlib.Path.is_dir', return_value=False):
            with pytest.raises(FileNotFoundError, match="Simulation directory not found"):
                Simul8Simulator('/invalid/path', sim_file)

    def test_init_with_missing_file(self, sim_path):
        """Test initialization with a missing simulation file raises FileNotFoundError."""
        with patch('src.core.simul8_simulator.Path') as mock_path_class:
            mock_path_instance = MagicMock()
            mock_path_instance.is_dir.return_value = True

            mock_file_path = MagicMock()
            mock_file_path.exists.return_value = False
            mock_path_instance.__truediv__ = MagicMock(
                return_value=mock_file_path)

            mock_path_class.return_value.resolve.return_value = mock_path_instance

            with pytest.raises(FileNotFoundError, match="Simulation file .* not found"):
                Simul8Simulator(sim_path, 'missing_file.s8')

    def test_init_with_non_s8_extension_logs_warning(self, sim_path):
        """Test initialization with non-.s8 file extension logs warning."""
        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.is_dir', return_value=True), \
                patch('pathlib.Path.is_file', return_value=True), \
                patch('src.core.simul8_simulator.logger') as mock_logger:

            # Test with various non-.s8 extensions
            test_files = ['simulation.txt', 'model.xml', 'test.s8x', 'file.S8X']

            for test_file in test_files:
                mock_logger.reset_mock()
                simulator = Simul8Simulator(sim_path, test_file)

                # Verify warning was logged
                mock_logger.warning.assert_called_once_with(
                    "Simulation file '%s' does not have .S8 extension", test_file)

                # Verify simulator was still created
                assert simulator.sim_file == test_file

    class TestStartMethod:
        """Tests for the start() method of Simul8Simulator."""

        def test_start_initializes_com_and_creates_instance(self, simulator):
            """Test that start() initializes COM and creates Simul8 instance."""
            with patch('src.core.simul8_simulator.pythoncom.CoInitialize') as mock_coinit, \
                    patch('src.core.simul8_simulator.Dispatch') as mock_dispatch, \
                    patch('src.core.simul8_simulator.client.WithEvents') as mock_events, \
                    patch('time.time', return_value=1000.0):

                mock_s8 = MagicMock()
                mock_dispatch.return_value = mock_s8
                mock_event_handler = MagicMock()
                mock_events.return_value = mock_event_handler

                simulator.start()

                # Verify COM was initialized
                mock_coinit.assert_called_once()

                # Verify Simul8 instance was created
                mock_dispatch.assert_called_once_with("Simul8.S8Simulation")
                assert simulator.s8 == mock_s8

                # Verify event handler was set up
                mock_events.assert_called_once()
                assert simulator.events == mock_event_handler

                # Verify start time was set
                assert simulator.start_time == pytest.approx(1000.0, rel=1e-9)

        def test_start_sets_start_time(self, simulator):
            """Test that start() sets the start_time attribute."""
            with patch('src.core.simul8_simulator.pythoncom.CoInitialize'), \
                    patch('src.core.simul8_simulator.Dispatch'), \
                    patch('src.core.simul8_simulator.client.WithEvents'), \
                    patch('time.time', return_value=12345.67):

                simulator.start()

                assert simulator.start_time == pytest.approx(12345.67, rel=1e-9)

        def test_start_creates_event_handler(self, simulator):
            """Test that start() creates and attaches event handler."""
            with patch('src.core.simul8_simulator.pythoncom.CoInitialize'), \
                    patch('src.core.simul8_simulator.Dispatch') as mock_dispatch, \
                    patch('src.core.simul8_simulator.client.WithEvents') as mock_events, \
                    patch.object(simulator, '_create_event_handler') as mock_create_handler, \
                    patch('time.time'):

                mock_s8 = MagicMock()
                mock_dispatch.return_value = mock_s8
                mock_handler_class = MagicMock()
                mock_create_handler.return_value = mock_handler_class

                simulator.start()

                # Verify event handler was created
                mock_create_handler.assert_called_once()

                # Verify WithEvents was called with s8 instance and handler
                # class
                mock_events.assert_called_once_with(mock_s8, mock_handler_class)

        def test_start_coinitialize_failure_raises_error(self, simulator):
            """Test that CoInitialize failure is handled properly."""
            with patch('src.core.simul8_simulator.pythoncom.CoInitialize',
                       side_effect=Exception("COM init failed")), \
                    patch.object(simulator, 'cleanup') as mock_cleanup, \
                    patch('time.time'):

                with pytest.raises(Simul8SimulationError, match="Failed to start Simul8 engine"):
                    simulator.start()

                # Verify cleanup was called
                mock_cleanup.assert_called_once()

        def test_start_dispatch_failure_raises_error(self, simulator):
            """Test that Dispatch failure is handled properly."""
            with patch('src.core.simul8_simulator.pythoncom.CoInitialize'), \
                    patch('src.core.simul8_simulator.Dispatch',
                          side_effect=Exception("Dispatch failed")), \
                    patch.object(simulator, 'cleanup') as mock_cleanup, \
                    patch('time.time'):

                with pytest.raises(Simul8SimulationError, match="Failed to start Simul8 engine"):
                    simulator.start()

                # Verify cleanup was called
                mock_cleanup.assert_called_once()

        def test_start_with_events_failure_raises_error(self, simulator):
            """Test that WithEvents failure is handled properly."""
            with patch('src.core.simul8_simulator.pythoncom.CoInitialize'), \
                    patch('src.core.simul8_simulator.Dispatch'), \
                    patch('src.core.simul8_simulator.client.WithEvents',
                          side_effect=Exception("Events failed")), \
                    patch.object(simulator, 'cleanup') as mock_cleanup, \
                    patch('time.time'):

                with pytest.raises(Simul8SimulationError, match="Failed to start Simul8 engine"):
                    simulator.start()

                # Verify cleanup was called
                mock_cleanup.assert_called_once()

        def test_start_exception_calls_cleanup(self, simulator):
            """Test that any exception during start triggers cleanup."""
            with patch('src.core.simul8_simulator.pythoncom.CoInitialize'), \
                    patch('src.core.simul8_simulator.Dispatch',
                          side_effect=RuntimeError("Unexpected error")), \
                    patch.object(simulator, 'cleanup') as mock_cleanup, \
                    patch('time.time'):

                with pytest.raises(Simul8SimulationError):
                    simulator.start()

                # Verify cleanup was called before re-raising
                mock_cleanup.assert_called_once()

        def test_start_logs_debug_messages(self, simulator):
            """Test that start() logs appropriate debug messages."""
            with patch('src.core.simul8_simulator.pythoncom.CoInitialize'), \
                    patch('src.core.simul8_simulator.Dispatch'), \
                    patch('src.core.simul8_simulator.client.WithEvents'), \
                    patch('time.time'), \
                    patch('src.core.simul8_simulator.logger') as mock_logger:

                simulator.start()

                # Verify debug messages were logged
                mock_logger.debug.assert_any_call("Starting Simul8 engine")
                mock_logger.debug.assert_any_call(
                    "Simul8 engine started successfully")


class TestParseOutputCSV:
    """Tests for _parse_output_csv method."""

    def test_parse_output_file_not_found(self, simulator):
        """Test error when output CSV doesn't exist."""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError, match="Output CSV not found"):
                simulator._parse_output_csv("/path/to/output.csv")

    def test_parse_output_empty_file(self, simulator):
        """Test error when CSV file is empty."""
        mock_file_content = ""

        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.open', mock_open(read_data=mock_file_content)):
            with pytest.raises(ValueError, match="CSV file is empty"):
                simulator._parse_output_csv("/path/to/output.csv")

    def test_parse_output_with_outputs_dict(self, simulator, valid_outputs):
        """Test parsing with output mapping."""
        csv_content = "Total CO2,Total Energy,Other\n125,456,789\n"

        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            result = simulator._parse_output_csv(
                "/path/to/output.csv", valid_outputs)

            assert result == {'total_co2': '125', 'total_energy': '456'}

    def test_parse_output_without_outputs(self, simulator):
        """Test parsing without output mapping returns empty dict."""
        csv_content = "Total CO2,Total Energy\n125,456\n"

        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            result = simulator._parse_output_csv("/path/to/output.csv", None)

            assert result == {}

    def test_parse_output_missing_mapped_column(self, simulator):
        """Test parsing when mapped column doesn't exist in CSV."""
        csv_content = "Total CO2,Other\n125,789\n"
        outputs = {'total_energy': 'Total Energy'}

        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            result = simulator._parse_output_csv("/path/to/output.csv", outputs)

            assert result == {'total_energy': '0'}

    def test_parse_output_empty_values(self, simulator, valid_outputs):
        """Test parsing with empty values defaults to '0'."""
        csv_content = "Total CO2,Total Energy\n,\n"

        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            result = simulator._parse_output_csv(
                "/path/to/output.csv", valid_outputs)

            assert result == {'total_co2': '0', 'total_energy': '0'}

    def test_parse_output_with_whitespace(self, simulator, valid_outputs):
        """Test parsing strips whitespace from headers and values."""
        csv_content = " Total CO2 , Total Energy \n 125 , 456 \n"

        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            result = simulator._parse_output_csv(
                "/path/to/output.csv", valid_outputs)

            assert result == {'total_co2': '125', 'total_energy': '456'}

    def test_parse_output_missing_data_row(self, simulator, valid_outputs):
        """Test parsing when only headers exist."""
        csv_content = "Total CO2,Total Energy\n"

        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            result = simulator._parse_output_csv(
                "/path/to/output.csv", valid_outputs)

            assert result == {'total_co2': '0', 'total_energy': '0'}

    def test_parse_output_list_outputs_returns_empty(self, simulator):
        """Test parsing with list outputs (not dict) returns empty dict."""
        csv_content = "Total CO2,Total Energy\n125,456\n"

        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            result = simulator._parse_output_csv(
                "/path/to/output.csv", ['total_co2'])

            # List is not a dict, so desired_outputs becomes {}
            assert result == {}


class TestRunMethod:
    """Tests for run method."""

    def test_run_no_file_path_specified(self, valid_inputs):
        """Test error when no file path is available."""
        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.is_dir', return_value=True), \
                patch('pathlib.Path.is_file', return_value=True):
            simulator = Simul8Simulator("path", "file.s8")
            simulator.sim_path = None
            simulator.sim_file = None

        with pytest.raises(Simul8SimulationError, match="No simulation file specified"):
            simulator.run(file_path=None, inputs=valid_inputs)

    def test_run_file_not_found(self, simulator, valid_inputs):
        """Test error when simulation file doesn't exist."""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError, match="Simulation file .* not found"):
                simulator.run(
                    file_path="/path/to/missing.s8",
                    inputs=valid_inputs)

    def test_run_uses_default_file_path(
            self, simulator, valid_inputs, valid_outputs):
        """Test run uses sim_path/sim_file when file_path not provided."""
        with patch('pathlib.Path.exists', return_value=True), \
                patch.object(simulator, '_prepare_inputs_to_csv', return_value=Path("input.csv")), \
                patch.object(simulator, '_run_simul8_engine', return_value=Path("output.csv")), \
                patch.object(simulator, '_parse_output_csv', return_value={'total_co2': '123'}), \
                patch.object(simulator, '_cleanup_temp_files'):

            result = simulator.run(inputs=valid_inputs, outputs=valid_outputs)

            expected_file_path = simulator.sim_path / simulator.sim_file
            assert simulator.actual_file_path == str(expected_file_path)
            assert result == {'total_co2': '123'}

    def test_run_full_workflow_success(
            self, simulator, valid_inputs, valid_outputs):
        """Test successful full run workflow."""
        input_csv_path = Path("/sim/input.csv")
        output_csv_path = Path("/sim/output.csv")
        expected_results = {'total_co2': '123', 'total_energy': '456'}

        with patch('pathlib.Path.exists', return_value=True), \
                patch.object(simulator, '_prepare_inputs_to_csv', return_value=input_csv_path) as mock_prepare, \
                patch.object(simulator, '_run_simul8_engine', return_value=output_csv_path) as mock_engine, \
                patch.object(simulator, '_parse_output_csv', return_value=expected_results) as mock_parse, \
                patch.object(simulator, '_cleanup_temp_files') as mock_cleanup:

            result = simulator.run(
                file_path="/sim/test.s8",
                inputs=valid_inputs,
                outputs=valid_outputs
            )

            # Verify workflow
            mock_prepare.assert_called_once_with(valid_inputs)
            mock_engine.assert_called_once()
            mock_parse.assert_called_once_with(output_csv_path, valid_outputs)
            mock_cleanup.assert_called_once()

            assert result == expected_results
            assert simulator.results == expected_results

    def test_run_uses_default_sim_path(self, simulator, valid_inputs):
        """Test that run uses sim_path/sim_file when file_path not provided."""
        expected_file_path = simulator.sim_path / simulator.sim_file

        with patch('pathlib.Path.exists', return_value=True), \
                patch.object(simulator, '_prepare_inputs_to_csv', return_value=Path("input.csv")), \
                patch.object(simulator, '_run_simul8_engine', return_value=Path("output.csv")), \
                patch.object(simulator, '_parse_output_csv', return_value={}), \
                patch.object(simulator, '_cleanup_temp_files'):

            simulator.run(inputs=valid_inputs)  # No file_path provided

            # Should use the default sim_path/sim_file
            assert Path(simulator.actual_file_path) == expected_file_path
            assert simulator.sim_path == expected_file_path.parent
            assert simulator.sim_file == expected_file_path.name

    def test_run_cleanup_fails_gracefully(self, simulator, valid_inputs):
        """Test that cleanup failures don't affect run success."""
        with patch('pathlib.Path.exists', return_value=True), \
                patch.object(simulator, '_prepare_inputs_to_csv', return_value=Path("input.csv")), \
                patch.object(simulator, '_run_simul8_engine', return_value=Path("output.csv")), \
                patch.object(simulator, '_parse_output_csv', return_value={'total_co2': '123'}), \
                patch.object(simulator, '_cleanup_temp_files', side_effect=Exception("Cleanup failed")):

            # Should not raise, just log the error
            result = simulator.run(
                file_path="/sim/test.s8",
                inputs=valid_inputs)

            assert result == {'total_co2': '123'}

    def test_run_engine_error_propagates(self, simulator, valid_inputs):
        """Test that engine errors are propagated."""
        with patch('pathlib.Path.exists', return_value=True), \
                patch.object(simulator, '_prepare_inputs_to_csv', return_value=Path("input.csv")), \
                patch.object(simulator, '_run_simul8_engine', side_effect=Simul8SimulationError("Engine failed")):

            with pytest.raises(Simul8SimulationError, match="Engine failed"):
                simulator.run(file_path="/sim/test.s8", inputs=valid_inputs)


class TestSetSimulationInputs:
    """Tests for _set_simulation_inputs method."""

    def test_set_inputs_no_inputs_provided(self, simulator):
        """Test that missing inputs raises error with helpful message."""
        with pytest.raises(Simul8SimulationError, match="No inputs provided"):
            simulator._set_simulation_inputs(None)

    def test_set_inputs_empty_dict(self, simulator):
        """Test that empty inputs dict raises error."""
        with pytest.raises(Simul8SimulationError, match="No inputs provided"):
            simulator._set_simulation_inputs({})

    def test_set_inputs_invalid_csv_structure(self, simulator):
        """Test that invalid CSV structure raises CSVFormatError."""
        invalid_inputs = {'columns': ['energy'], 'r1': ['100', '200']}

        with patch('src.core.simul8_simulator.validate_csv_structure',
                   side_effect=CSVFormatError("Invalid structure")):
            with pytest.raises(Simul8SimulationError, match="Error creating input file"):
                simulator._set_simulation_inputs(invalid_inputs)

    def test_set_inputs_with_actual_file_path(self, simulator, valid_inputs):
        """Test input creation when actual_file_path is set."""
        sim_dir = str(Path("/path/to/sim"))
        simulator.actual_file_path = str(Path(sim_dir) / "file.s8")
        expected_input_path = str(Path(sim_dir) / "input.csv")

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('os.path.isdir', return_value=True), \
                patch('src.core.simul8_simulator.yaml_csv_to_file') as mock_write, \
                patch('os.path.exists', return_value=True), \
                patch('builtins.open', mock_open(read_data="col1,col2\nval1,val2\n")):

            simulator._set_simulation_inputs(valid_inputs)

            # Verify yaml_csv_to_file was called with correct path
            mock_write.assert_called_once_with(
                valid_inputs, file_path=expected_input_path)

    def test_set_inputs_with_sim_path(self, simulator, valid_inputs):
        """Test input creation using sim_path when actual_file_path not set."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        expected_input_path = str(simulator.sim_path / "input.csv")

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('os.path.isdir', return_value=True), \
                patch('src.core.simul8_simulator.yaml_csv_to_file') as mock_write, \
                patch('os.path.exists', return_value=True), \
                patch('builtins.open', mock_open(read_data="col1,col2\nval1,val2\n")):

            simulator._set_simulation_inputs(valid_inputs)

            mock_write.assert_called_once_with(
                valid_inputs, file_path=expected_input_path)

    def test_set_inputs_prefers_actual_file_path(self, simulator, valid_inputs):
        """Test that actual_file_path takes precedence over sim_path."""
        sim_dir = "/actual/path"
        simulator.actual_file_path = str(Path(sim_dir) / "test.s8")
        # sim_path also exists but should be ignored
        simulator.sim_path = Path("/other/path")

        expected_input_path = str(Path(sim_dir) / "input.csv")

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('os.path.isdir', return_value=True), \
                patch('src.core.simul8_simulator.yaml_csv_to_file') as mock_write, \
                patch('os.path.exists', return_value=True), \
                patch('builtins.open', mock_open(read_data="data")):

            simulator._set_simulation_inputs(valid_inputs)

            # Should use actual_file_path directory
            mock_write.assert_called_once_with(
                valid_inputs, file_path=expected_input_path)

    def test_set_inputs_no_determinable_directory(self, valid_inputs):
        """Test error when directory cannot be determined."""
        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.is_dir', return_value=True), \
                patch('pathlib.Path.is_file', return_value=True):
            simulator = Simul8Simulator("path", "file.s8")
            simulator.sim_path = None
            simulator.sim_file = None
            if hasattr(simulator, 'actual_file_path'):
                delattr(simulator, 'actual_file_path')

        with patch('src.core.simul8_simulator.validate_csv_structure'):
            with pytest.raises(Simul8SimulationError, match="Could not determine simulation directory"):
                simulator._set_simulation_inputs(valid_inputs)

    def test_set_inputs_directory_not_exists(self, simulator, valid_inputs):
        """Test error when simulation directory doesn't exist."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('os.path.isdir', return_value=False):
            with pytest.raises(Simul8SimulationError, match="Error creating input file"):
                simulator._set_simulation_inputs(valid_inputs)

    def test_set_inputs_file_creation_fails(self, simulator, valid_inputs):
        """Test error when CSV file creation fails."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('os.path.isdir', return_value=True), \
                patch('src.core.simul8_simulator.yaml_csv_to_file'), \
                patch('os.path.exists', return_value=False):

            with pytest.raises(Simul8SimulationError, match="Failed to create input.csv"):
                simulator._set_simulation_inputs(valid_inputs)

    def test_set_inputs_yaml_csv_to_file_raises_error(
            self, simulator, valid_inputs):
        """Test that errors from yaml_csv_to_file are wrapped."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
            patch('os.path.isdir', return_value=True), \
            patch('src.core.simul8_simulator.yaml_csv_to_file',
                  side_effect=IOError("Write failed")):

            with pytest.raises(Simul8SimulationError, match="Error creating input file"):
                simulator._set_simulation_inputs(valid_inputs)

    def test_set_inputs_logs_parameter_count(self, simulator, valid_inputs):
        """Test that parameter count is logged."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('os.path.isdir', return_value=True), \
                patch('src.core.simul8_simulator.yaml_csv_to_file'), \
                patch('os.path.exists', return_value=True), \
                patch('builtins.open', mock_open(read_data="data")), \
                patch('src.core.simul8_simulator.logger') as mock_logger:

            simulator._set_simulation_inputs(valid_inputs)

            # Verify info log was called with parameter count
            mock_logger.info.assert_any_call(
                "Processing %d input parameters", len(valid_inputs))

    def test_set_inputs_logs_file_path(self, simulator, valid_inputs):
        """Test that created file path is logged."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        expected_path = str(simulator.sim_path / "input.csv")

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('os.path.isdir', return_value=True), \
                patch('src.core.simul8_simulator.yaml_csv_to_file'), \
                patch('os.path.exists', return_value=True), \
                patch('builtins.open', mock_open(read_data="data")), \
                patch('src.core.simul8_simulator.logger') as mock_logger:

            simulator._set_simulation_inputs(valid_inputs)

            # Verify debug log was called with file path
            mock_logger.debug.assert_any_call(
                "Created input file at: %s", expected_path)

    def test_set_inputs_logs_file_content(self, simulator, valid_inputs):
        """Test that file content is logged for debugging."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        csv_content = "energy,co2\n100,50\n200,75\n"

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('os.path.isdir', return_value=True), \
                patch('src.core.simul8_simulator.yaml_csv_to_file'), \
                patch('os.path.exists', return_value=True), \
                patch('builtins.open', mock_open(read_data=csv_content)), \
                patch('src.core.simul8_simulator.logger') as mock_logger:

            simulator._set_simulation_inputs(valid_inputs)

            # Verify file content was logged
            mock_logger.debug.assert_any_call("File content:\n%s", csv_content)

    def test_set_inputs_wraps_all_exceptions(self, simulator, valid_inputs):
        """Test that all exceptions are wrapped in Simul8SimulationError."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('os.path.isdir', side_effect=RuntimeError("Unexpected error")):

            with pytest.raises(Simul8SimulationError, match="Error creating input file"):
                simulator._set_simulation_inputs(valid_inputs)

    def test_set_inputs_logs_errors(self, simulator, valid_inputs):
        """Test that errors are logged before being raised."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('os.path.isdir', return_value=True), \
                patch('src.core.simul8_simulator.yaml_csv_to_file',
                      side_effect=IOError("Write failed")), \
                patch('src.core.simul8_simulator.logger') as mock_logger:

            with pytest.raises(Simul8SimulationError):
                simulator._set_simulation_inputs(valid_inputs)

            # Verify error was logged
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "Failed to create input file" in call_args[0][0]
            assert call_args[1]['exc_info'] is True

    def test_set_inputs_with_complex_csv_structure(self, simulator):
        """Test with multiple rows of data."""
        complex_inputs = {
            'columns': ['energy', 'co2', 'water'],
            'r1': ['100', '50', '20'],
            'r2': ['200', '75', '30'],
            'r3': ['150', '60', '25']
        }

        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('os.path.isdir', return_value=True), \
                patch('src.core.simul8_simulator.yaml_csv_to_file') as mock_write, \
                patch('os.path.exists', return_value=True), \
                patch('builtins.open', mock_open(read_data="data")):

            simulator._set_simulation_inputs(complex_inputs)

            # Verify correct data was passed
            mock_write.assert_called_once_with(
                complex_inputs, file_path=mock_write.call_args[1]['file_path'])

    def test_set_inputs_creates_file_in_correct_location(
            self, simulator, valid_inputs):
        """Test that input.csv is created next to simulation file."""
        sim_dir = "/test/sim/dir"
        simulator.actual_file_path = str(Path(sim_dir) / "simulation.s8")

        captured_path = None

        def capture_write(data, file_path):
            nonlocal captured_path
            captured_path = file_path

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('os.path.isdir', return_value=True), \
                patch('src.core.simul8_simulator.yaml_csv_to_file', side_effect=capture_write), \
                patch('os.path.exists', return_value=True), \
                patch('builtins.open', mock_open(read_data="data")):

            simulator._set_simulation_inputs(valid_inputs)

            # Verify path is correct
            assert captured_path == str(Path(sim_dir) / "input.csv")
            assert captured_path.endswith("input.csv")


class TestEventHandler:
    """Tests for the event handler created in _create_event_handler."""

    def test_event_handler_runsim_called_with_run_time(self, simulator):
        """Test that OnS8SimulationOpened calls RunSim with run_time."""
        # Set up the simulator with required attributes
        simulator.run_time = 1234
        simulator.s8 = MagicMock()
        simulator.listen_for_messages = True

        # Create the event handler class
        EventHandler = simulator._create_event_handler()
        handler = EventHandler()

        # Call the event that should start the simulation
        handler.OnS8SimulationOpened()

        # Verify RunSim was called with the correct run_time
        simulator.s8.RunSim.assert_called_once_with(1234)

    def test_event_handler_end_run_stops_listening(self, simulator):
        """Test that OnS8SimulationEndRun stops the message loop."""
        # Set up the simulator
        simulator.run_time = 1
        simulator.s8 = MagicMock()
        simulator.listen_for_messages = True

        # Create the event handler class
        event_handler = simulator._create_event_handler()
        handler = event_handler()

        # Call the end run event
        handler.OnS8SimulationEndRun()

        # Verify the flag was flipped to stop the message loop
        assert simulator.listen_for_messages is False

    def test_event_handler_maintains_simulator_reference(self, simulator):
        """Test that event handler correctly references the simulator instance."""
        simulator.run_time = 500
        simulator.s8 = MagicMock()
        simulator.listen_for_messages = True

        event_handler = simulator._create_event_handler()
        handler = event_handler()

        # Trigger event and verify it affects the original simulator
        handler.OnS8SimulationOpened()

        # The handler should have access to simulator's attributes
        simulator.s8.RunSim.assert_called_once_with(500)

    def test_event_handler_multiple_instances(self, simulator):
        """Test that multiple handler instances share the same simulator reference."""
        simulator.run_time = 100
        simulator.s8 = MagicMock()
        simulator.listen_for_messages = True

        event_handler = simulator._create_event_handler()
        handler1 = event_handler()
        handler2 = event_handler()

        # First handler starts simulation
        handler1.OnS8SimulationOpened()

        # Second handler ends simulation
        handler2.OnS8SimulationEndRun()

        # Both should affect the same simulator
        simulator.s8.RunSim.assert_called_once_with(100)
        assert simulator.listen_for_messages is False

    def test_event_handler_with_zero_run_time(self, simulator):
        """Test event handler with zero run_time."""
        simulator.run_time = 0
        simulator.s8 = MagicMock()
        simulator.listen_for_messages = True

        event_handler = simulator._create_event_handler()
        handler = event_handler()

        handler.OnS8SimulationOpened()

        # Should still call RunSim even with 0
        simulator.s8.RunSim.assert_called_once_with(0)

    def test_event_handler_end_run_already_stopped(self, simulator):
        """Test OnS8SimulationEndRun when already stopped."""
        simulator.run_time = 1
        simulator.s8 = MagicMock()
        simulator.listen_for_messages = False  # Already stopped

        event_handler = simulator._create_event_handler()
        handler = event_handler()

        # Should still work without error
        handler.OnS8SimulationEndRun()

        assert simulator.listen_for_messages is False


class TestPrepareInputsToCSV:
    """Tests for _prepare_inputs_to_csv method."""

    def test_prepare_inputs_no_inputs_provided(self, simulator):
        """Test that missing inputs raises error."""
        with pytest.raises(Simul8SimulationError, match="No inputs provided"):
            simulator._prepare_inputs_to_csv(None)

    def test_prepare_inputs_empty_dict(self, simulator):
        """Test that empty inputs dict raises error."""
        with pytest.raises(Simul8SimulationError, match="No inputs provided"):
            simulator._prepare_inputs_to_csv({})

    def test_prepare_inputs_invalid_csv_structure(self, simulator):
        """Test that invalid CSV structure raises CSVFormatError."""
        invalid_inputs = {
            'columns': ['energy'], 'r1': [
                '100', '200']}  # Mismatch

        with patch('src.core.simul8_simulator.validate_csv_structure',
                   side_effect=CSVFormatError("Invalid structure")):
            with pytest.raises(CSVFormatError, match="Invalid structure"):
                simulator._prepare_inputs_to_csv(invalid_inputs)

    def test_prepare_inputs_with_actual_file_path(
            self, simulator, valid_inputs):
        """Test CSV preparation when actual_file_path is set."""
        simulator.actual_file_path = str(Path("/path/to/sim/file.s8"))

        mock_input_path = MagicMock()
        mock_input_path.exists.return_value = True

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.is_dir', return_value=True), \
                patch('pathlib.Path.__truediv__', return_value=mock_input_path), \
                patch('src.core.simul8_simulator.yaml_csv_to_file') as mock_write:

            result = simulator._prepare_inputs_to_csv(valid_inputs)

            assert result == mock_input_path
            mock_write.assert_called_once()
            # Verify it was called with the inputs and correct path
            call_args = mock_write.call_args
            assert call_args[0][0] == valid_inputs
            assert 'file_path' in call_args[1]

    def test_prepare_inputs_with_sim_path(self, simulator, valid_inputs):
        """Test CSV preparation using sim_path and sim_file."""
        # Ensure actual_file_path is not set
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        mock_input_path = MagicMock()
        mock_input_path.exists.return_value = True

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.is_dir', return_value=True), \
                patch('pathlib.Path.__truediv__', return_value=mock_input_path), \
                patch('src.core.simul8_simulator.yaml_csv_to_file') as mock_write:

            result = simulator._prepare_inputs_to_csv(valid_inputs)

            assert result == mock_input_path
            mock_write.assert_called_once_with(
                valid_inputs, file_path=str(mock_input_path))

    def test_prepare_inputs_no_determinable_directory(self, valid_inputs):
        """Test error when directory cannot be determined."""
        # Create simulator without path info
        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.is_dir', return_value=True), \
                patch('pathlib.Path.is_file', return_value=True):
            simulator = Simul8Simulator("path", "file.s8")
            simulator.sim_path = None
            simulator.sim_file = None
            if hasattr(simulator, 'actual_file_path'):
                delattr(simulator, 'actual_file_path')

        with patch('src.core.simul8_simulator.validate_csv_structure'):
            with pytest.raises(Simul8SimulationError, match="Could not determine directory"):
                simulator._prepare_inputs_to_csv(valid_inputs)

    def test_prepare_inputs_sim_path_none_but_sim_file_exists(
            self, valid_inputs):
        """Test error when sim_path is None even if sim_file exists."""
        with patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.is_dir', return_value=True), \
                patch('pathlib.Path.is_file', return_value=True):
            simulator = Simul8Simulator("path", "file.s8")
            simulator.sim_path = None
            simulator.sim_file = "test.s8"
            if hasattr(simulator, 'actual_file_path'):
                delattr(simulator, 'actual_file_path')

        with patch('src.core.simul8_simulator.validate_csv_structure'):
            with pytest.raises(Simul8SimulationError, match="Could not determine directory"):
                simulator._prepare_inputs_to_csv(valid_inputs)

    def test_prepare_inputs_directory_not_exists(self, simulator, valid_inputs):
        """Test error when simulation directory doesn't exist."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('pathlib.Path.exists', return_value=False), \
                patch('pathlib.Path.is_dir', return_value=False):
            with pytest.raises(FileNotFoundError, match="Simulation directory not found"):
                simulator._prepare_inputs_to_csv(valid_inputs)

    def test_prepare_inputs_path_is_not_directory(
            self, simulator, valid_inputs):
        """Test error when path exists but is not a directory."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.is_dir', return_value=False):
            with pytest.raises(FileNotFoundError, match="Simulation directory not found"):
                simulator._prepare_inputs_to_csv(valid_inputs)

    def test_prepare_inputs_csv_write_fails(self, simulator, valid_inputs):
        """Test error when CSV file creation fails."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        mock_input_path = MagicMock()
        mock_input_path.exists.return_value = False  # File doesn't exist after write

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.is_dir', return_value=True), \
                patch('pathlib.Path.__truediv__', return_value=mock_input_path), \
                patch('src.core.simul8_simulator.yaml_csv_to_file'):

            with pytest.raises(Simul8SimulationError, match="Failed to create input.csv"):
                simulator._prepare_inputs_to_csv(valid_inputs)

    def test_prepare_inputs_yaml_csv_to_file_raises_error(
            self, simulator, valid_inputs):
        """Test that errors from yaml_csv_to_file are propagated."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
            patch('pathlib.Path.exists', return_value=True), \
            patch('pathlib.Path.is_dir', return_value=True), \
            patch('src.core.simul8_simulator.yaml_csv_to_file',
                  side_effect=IOError("Write failed")):

            with pytest.raises(IOError, match="Write failed"):
                simulator._prepare_inputs_to_csv(valid_inputs)

    def test_prepare_inputs_creates_input_csv_in_correct_location(
            self, simulator, valid_inputs):
        """Test that input.csv is created next to the simulation file."""
        sim_dir = Path("/test/sim/dir")
        simulator.actual_file_path = str(sim_dir / "test.s8")

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.is_dir', return_value=True), \
                patch('src.core.simul8_simulator.yaml_csv_to_file') as mock_write:

            result = simulator._prepare_inputs_to_csv(valid_inputs)

            # Check that yaml_csv_to_file was called
            mock_write.assert_called_once()

            # Verify the inputs were passed
            assert mock_write.call_args[0][0] == valid_inputs

            # Verify file_path parameter contains "input.csv"
            file_path_arg = mock_write.call_args[1]['file_path']
            assert 'input.csv' in file_path_arg

            # Verify result is a Path pointing to input.csv
            assert result.name == 'input.csv'

    def test_prepare_inputs_returns_path_object(self, simulator, valid_inputs):
        """Test that method returns a Path object."""
        if hasattr(simulator, 'actual_file_path'):
            delattr(simulator, 'actual_file_path')

        mock_input_path = MagicMock(spec=Path)
        mock_input_path.exists.return_value = True

        with patch('src.core.simul8_simulator.validate_csv_structure'), \
                patch('pathlib.Path.exists', return_value=True), \
                patch('pathlib.Path.is_dir', return_value=True), \
                patch('pathlib.Path.__truediv__', return_value=mock_input_path), \
                patch('src.core.simul8_simulator.yaml_csv_to_file'):

            result = simulator._prepare_inputs_to_csv(valid_inputs)

            # Should return the Path object
            assert result is mock_input_path


class TestCleanupTempFiles:
    """Tests for _cleanup_temp_files method."""

    def test_cleanup_with_actual_file_path(self, simulator):
        """Test cleanup uses actual_file_path when available."""
        simulator.actual_file_path = "/sim/dir/test.s8"

        mock_input = MagicMock()
        mock_input.exists.return_value = True
        mock_output = MagicMock()
        mock_output.exists.return_value = True

        with patch('pathlib.Path.__truediv__', side_effect=[mock_input, mock_output]):
            simulator._cleanup_temp_files()

            mock_input.unlink.assert_called_once()
            mock_output.unlink.assert_called_once()

    def test_cleanup_with_sim_path(self, simulator):
        """Test cleanup uses sim_path when actual_file_path not set."""
        mock_input = MagicMock()
        mock_input.exists.return_value = True
        mock_output = MagicMock()
        mock_output.exists.return_value = False

        with patch('pathlib.Path.__truediv__', side_effect=[mock_input, mock_output]):
            simulator._cleanup_temp_files()

            mock_input.unlink.assert_called_once()
            mock_output.unlink.assert_not_called()

    def test_cleanup_handles_exceptions(self, simulator):
        """Test cleanup handles file deletion errors gracefully."""
        mock_input = MagicMock()
        mock_input.exists.return_value = True
        mock_input.unlink.side_effect = PermissionError("Cannot delete")
        mock_output = MagicMock()
        mock_output.exists.return_value = True

        with patch('pathlib.Path.__truediv__', side_effect=[mock_input, mock_output]):
            # Should not raise exception
            simulator._cleanup_temp_files()

            mock_input.unlink.assert_called_once()
            mock_output.unlink.assert_called_once()


class TestGetMetadata:
    """Tests for get_metadata method."""

    def test_get_metadata_with_execution_time(self, simulator):
        """Test metadata includes execution time when available."""
        simulator.start_time = 1000.0
        with patch('time.time', return_value=1010.0):
            metadata = simulator.get_metadata()

            assert 'execution_time' in metadata
            assert metadata['execution_time'] == pytest.approx(10.0, rel=1e-5)

    def test_get_metadata_without_start_time(self, simulator):
        """Test metadata when start_time not set."""
        simulator.start_time = None

        metadata = simulator.get_metadata()

        assert 'execution_time' not in metadata

    def test_get_metadata_with_simul8_version(self, simulator):
        """Test metadata includes Simul8 version when available."""
        simulator.start_time = None
        mock_s8 = MagicMock()
        mock_s8.Version = "2023.1"
        simulator.s8 = mock_s8

        metadata = simulator.get_metadata()

        assert metadata.get('simul8_version') == "2023.1"

    def test_get_metadata_version_error(self, simulator):
        """Test metadata handles version retrieval error."""
        simulator.start_time = None

        class BadS8:
            @property
            def Version(self):
                raise Exception("COM error")
        simulator.s8 = BadS8()

        # Should not raise, just log warning
        metadata = simulator.get_metadata()

        assert 'simul8_version' not in metadata


class TestForceKillSimul8Processes:
    """Tests for force_kill_simul8_processes method."""

    def test_kills_simul8_processes(self, simulator):
        """Test that Simul8 processes are identified and terminated."""
        # Create mock processes
        mock_proc1 = MagicMock()
        mock_proc1.info = {
            'pid': 1234,
            'name': 's8.exe',
            'exe': '/path/to/s8.exe'}

        mock_proc2 = MagicMock()
        mock_proc2.info = {
            'pid': 5678,
            'name': 's8.exe',
            'exe': '/path/to/s8.exe'}

        mock_proc3 = MagicMock()
        mock_proc3.info = {
            'pid': 9999,
            'name': 'chrome.exe',
            'exe': '/path/to/chrome.exe'}

        # First process_iter call returns processes to terminate
        # Second process_iter call checks if they're still running
        mock_proc1.is_running.return_value = False  # Terminated gracefully
        mock_proc2.is_running.return_value = True   # Still running, needs force kill

        with patch('psutil.process_iter', side_effect=[
            [mock_proc1, mock_proc2, mock_proc3],  # First iteration
            [mock_proc1, mock_proc2]                # Second iteration
        ]), patch('time.sleep'):
            simulator.force_kill_simul8_processes()

            # Verify terminate was called on Simul8 processes
            mock_proc1.terminate.assert_called_once()
            mock_proc2.terminate.assert_called_once()
            mock_proc3.terminate.assert_not_called()

            # Verify force kill was only called on still-running process
            mock_proc1.kill.assert_not_called()
            mock_proc2.kill.assert_called_once()

    def test_handles_process_not_found_during_terminate(self, simulator):
        """Test graceful handling when process disappears during terminate."""
        mock_proc = MagicMock()
        mock_proc.info = {
            'pid': 1234,
            'name': 'S8.exe',
            'exe': '/path/to/s8.exe'}
        mock_proc.terminate.side_effect = psutil.NoSuchProcess(1234)

        with patch('psutil.process_iter', side_effect=[
            [mock_proc],  # First iteration
            []            # Second iteration (process gone)
        ]), patch('time.sleep'):
            # Should not raise exception
            simulator.force_kill_simul8_processes()

            mock_proc.terminate.assert_called_once()

    def test_handles_access_denied_during_terminate(self, simulator):
        """Test graceful handling when access is denied."""
        mock_proc = MagicMock()
        mock_proc.info = {
            'pid': 1234,
            'name': 'S8.exe',
            'exe': '/path/to/s8.exe'}
        mock_proc.terminate.side_effect = psutil.AccessDenied(1234)

        with patch('psutil.process_iter', side_effect=[
            [mock_proc],
            []
        ]), patch('time.sleep'):
            # Should not raise exception
            simulator.force_kill_simul8_processes()

            mock_proc.terminate.assert_called_once()

    def test_no_simul8_processes_found(self, simulator):
        """Test when no Simul8 processes are running."""
        mock_proc1 = MagicMock()
        mock_proc1.info = {
            'pid': 1111,
            'name': 'chrome.exe',
            'exe': '/path/to/chrome.exe'}

        mock_proc2 = MagicMock()
        mock_proc2.info = {
            'pid': 2222,
            'name': 'notepad.exe',
            'exe': '/path/to/notepad.exe'}

        with patch('psutil.process_iter', return_value=[mock_proc1, mock_proc2]), \
                patch('time.sleep') as mock_sleep:
            simulator.force_kill_simul8_processes()

            # No processes should be terminated
            mock_proc1.terminate.assert_not_called()
            mock_proc2.terminate.assert_not_called()

            # Sleep should not be called (no processes to wait for)
            mock_sleep.assert_not_called()

    def test_identifies_all_simul8_name_variations(self, simulator):
        """Test that all Simul8 name variations are identified."""
        mock_procs = []
        simul8_names = ['s8.exe', 'S8.EXE', 'test_s8.exe']

        for i, name in enumerate(simul8_names):
            proc = MagicMock()
            proc.info = {
                'pid': 1000 + i,
                'name': name,
                'exe': f'/path/to/{name}'}
            proc.is_running.return_value = False
            mock_procs.append(proc)

        with patch('psutil.process_iter', side_effect=[mock_procs, mock_procs]), \
                patch('time.sleep'):
            simulator.force_kill_simul8_processes()

            # All should be terminated
            for proc in mock_procs:
                proc.terminate.assert_called_once()

    def test_handles_process_disappears_before_force_kill(self, simulator):
        """Test when process terminates between iterations."""
        mock_proc = MagicMock()
        mock_proc.info = {
            'pid': 1234,
            'name': 'S8.exe',
            'exe': '/path/to/s8.exe'}
        mock_proc.is_running.side_effect = psutil.NoSuchProcess(1234)

        with patch('psutil.process_iter', side_effect=[
            [mock_proc],  # First iteration
            [mock_proc]   # Second iteration - but process gone when checked
        ]), patch('time.sleep'):
            # Should not raise exception
            simulator.force_kill_simul8_processes()

            mock_proc.terminate.assert_called_once()
            mock_proc.kill.assert_not_called()  # NoSuchProcess caught

    def test_handles_access_denied_during_force_kill(self, simulator):
        """Test graceful handling when force kill access is denied."""
        mock_proc = MagicMock()
        mock_proc.info = {
            'pid': 1234,
            'name': 'S8.exe',
            'exe': '/path/to/s8.exe'}
        mock_proc.is_running.return_value = True
        mock_proc.kill.side_effect = psutil.AccessDenied(1234)

        with patch('psutil.process_iter', side_effect=[
            [mock_proc],
            [mock_proc]
        ]), patch('time.sleep'):
            # Should not raise exception
            simulator.force_kill_simul8_processes()

            mock_proc.terminate.assert_called_once()
            mock_proc.kill.assert_called_once()

    def test_handles_unexpected_exception(self, simulator):
        """Test graceful handling of unexpected exceptions."""
        with patch('psutil.process_iter', side_effect=RuntimeError("Unexpected error")):
            # Should not raise exception, just log error
            simulator.force_kill_simul8_processes()
            # Method completes without error


class TestCleanupMethod:
    """Tests for the cleanup() method of Simul8Simulator."""

    def test_cleanup_closes_and_uninitializes(self, simulator):
        s8_mock = MagicMock()
        simulator.s8 = s8_mock
        simulator.events = MagicMock()

        with patch('src.core.simul8_simulator.gc.collect') as mock_gc, \
                patch('src.core.simul8_simulator.time.sleep') as mock_sleep, \
                patch('src.core.simul8_simulator.pythoncom.CoUninitialize') as mock_uninit, \
                patch.object(simulator, 'force_kill_simul8_processes') as mock_force:

            # Should not raise
            simulator.cleanup()

        s8_mock.Close.assert_called_once()
        assert simulator.s8 is None
        assert getattr(simulator, 'events', None) is None
        mock_gc.assert_called_once()
        mock_uninit.assert_called_once()
        mock_force.assert_called_once()

    def test_cleanup_close_raises_still_uninitializes_and_forces(
            self, simulator):
        s8_mock = MagicMock()
        s8_mock.Close.side_effect = Exception("close failed")
        simulator.s8 = s8_mock

        with patch('src.core.simul8_simulator.gc.collect'), \
                patch('src.core.simul8_simulator.time.sleep'), \
                patch('src.core.simul8_simulator.pythoncom.CoUninitialize') as mock_uninit, \
                patch.object(simulator, 'force_kill_simul8_processes') as mock_force:

            # Close raises, but cleanup should proceed without raising
            simulator.cleanup()

        mock_uninit.assert_called_once()
        mock_force.assert_called_once()
        assert simulator.s8 is None

    def test_cleanup_uninitialize_raises_but_force_kill_runs(self, simulator):
        s8_mock = MagicMock()
        simulator.s8 = s8_mock

        with patch('src.core.simul8_simulator.gc.collect'), \
                patch('src.core.simul8_simulator.time.sleep'), \
                patch('src.core.simul8_simulator.pythoncom.CoUninitialize',
                      side_effect=Exception("uninit failed")), \
                patch.object(simulator, 'force_kill_simul8_processes') as mock_force:

            simulator.cleanup()

        mock_force.assert_called_once()
        assert simulator.s8 is None

    def test_cleanup_force_kill_failure_is_handled(self, simulator):
        s8_mock = MagicMock()
        simulator.s8 = s8_mock

        with patch('src.core.simul8_simulator.gc.collect'), \
                patch('src.core.simul8_simulator.time.sleep'), \
                patch('src.core.simul8_simulator.pythoncom.CoUninitialize'), \
                patch.object(simulator, 'force_kill_simul8_processes', side_effect=Exception("force fail")):

            simulator.cleanup()

        assert simulator.s8 is None
