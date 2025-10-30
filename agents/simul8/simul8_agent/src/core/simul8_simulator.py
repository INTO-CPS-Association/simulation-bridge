"""
simul8_simulator.py - Simul8 COM Interface for Simulations

This module provides a class for interfacing with Simul8 via COM to run discrete event simulations.
It handles the lifecycle of Simul8 application instances, event handling, result collection,
and proper resource management.

Part of the simulation service infrastructure that enables distributed
Simul8 computational workloads.
"""

import os
import time

import subprocess
import csv
from pathlib import Path
import gc
from typing import Dict, List, Optional, Any, Union, cast
import pythoncom
from win32com import client
from win32com.client import Dispatch
import psutil


from ..utils.csv_parser import validate_csv_structure
from ..utils.logger import get_logger
from ..utils.csv_parser import yaml_csv_to_file

# Configure logger
logger = get_logger()


class Simul8SimulationError(Exception):
    """Custom exception for Simul8 simulation errors."""


class Simul8Simulator:
    """
    Manages the lifecycle of a Simul8 simulation with proper resource management,
    event handling and result collection.
    """

    def __init__(
            self,
            path: str = None,
            file: str = None,
            run_time: int = 1000) -> None:
        """
        Initialize a Simul8 simulator.

        Args:
            path: Directory path containing the simulation file (optional)
            file: Name of the Simul8 simulation file (.S8)
            run_time: Simulation run time in minutes (default: 1000)
        """
        self.sim_path = Path(path).resolve() if path else None
        self.sim_file = file
        self.run_time = run_time
        self.s8 = None
        self.events = None
        self.listen_for_messages = True
        self.start_time = None
        self.results = {}
        self.expected_outputs = {}

        if self.sim_path and self.sim_file:
            self._validate()

    def _validate(self) -> None:
        """Validate the simulation path and file."""
        if not self.sim_path.is_dir():
            raise FileNotFoundError(
                f"Simulation directory not found: {self.sim_path}")

        sim_file_path = self.sim_path / self.sim_file
        if not sim_file_path.exists():
            raise FileNotFoundError(
                f"Simulation file '{self.sim_file}' not found at {self.sim_path}")

        if not str(sim_file_path).lower().endswith('.s8'):
            logger.warning(
                "Simulation file '%s' does not have .S8 extension", self.sim_file)

    def start(self) -> None:
        """Initialize COM and create Simul8 instance."""
        logger.debug("Starting Simul8 engine")
        try:
            self.start_time = time.time()

            # Initialize COM Libraries
            pythoncom.CoInitialize()

            self.s8 = Dispatch("Simul8.S8Simulation")

            # Set up event handling
            self.events = client.WithEvents(
                self.s8, self._create_event_handler())

            logger.debug("Simul8 engine started successfully")
        except Exception as e:
            logger.error("Failed to start Simul8 engine: %s", str(e))
            self.cleanup()
            raise Simul8SimulationError(
                f"Failed to start Simul8 engine: {str(e)}"
            ) from e

    def _create_event_handler(self):
        """Create an event handler class for this simulation instance."""
        simulation = self

        class EventHandler:
            def OnS8SimulationOpened(self):
                logger.info("The Simulation has been opened.")
                # simulation.s8.RunSim(simulation.run_time)
                simulation.s8.RunSim(simulation.run_time)

            def OnS8SimulationEndRun(self):
                logger.info("The simulation run has ended.")
                simulation.listen_for_messages = False

        return EventHandler

    def _run_simul8_engine(
            self, sim_file_path: Union[str, Path], input_csv: Path) -> Path:
        """
        Run Simul8 with the provided sim file and input CSV. Returns the output CSV path.
        Raises Simul8SimulationError on failures.
        """
        # Ensure started
        if self.s8 is None:
            self.start()

        # Store actual file path and set working dir
        self.actual_file_path = str(sim_file_path)
        sim_dir = os.path.dirname(self.actual_file_path)
        original_cwd = os.getcwd()
        try:
            os.chdir(sim_dir)

            self.s8.Open(self.actual_file_path)

            # Run message loop
            self.listen_for_messages = True
            while self.listen_for_messages:
                pythoncom.PumpWaitingMessages()

            # After run, look for OUTPUT.csv
            output_path = Path(sim_dir) / "OUTPUT.csv"
            if not output_path.exists():
                raise Simul8SimulationError(
                    f"Output file not found after run: {output_path}")
            return output_path
        except Exception as e:
            raise Simul8SimulationError(
                f"Error running Simul8 engine: {e}") from e
        finally:
            os.chdir(original_cwd)

    def _set_simulation_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Write simulation inputs to input.csv file in the same directory as the S8 file.

        Args:
            inputs: Dictionary of input values with CSV structure

        Raises:
            Simul8SimulationError: If inputs are invalid or file creation fails
        """

        if not inputs:
            raise Simul8SimulationError(
                "No inputs provided - Simul8 simulation requires input data with structure: "
                "{'columns': ['col1', 'col2'], 'r1': ['val1', 'val2'], ...}"
            )

        logger.info("Processing %d input parameters", len(inputs))

        try:
            # Validate that inputs have the correct CSV structure
            validate_csv_structure(inputs)

            # Determine where the S8 file is located (strict: no fallback)
            if hasattr(self, 'actual_file_path') and getattr(
                    self, 'actual_file_path', None):
                sim_directory = os.path.dirname(self.actual_file_path)
            elif self.sim_path and self.sim_file:
                sim_directory = str(self.sim_path)
            else:
                raise Simul8SimulationError(
                    "Could not determine simulation directory. Provide 'path' and 'file' "
                    "when creating Simul8Simulator or set 'actual_file_path' before creating inputs."
                )

            if not os.path.isdir(sim_directory):
                raise FileNotFoundError(
                    f"Simulation directory not found: {sim_directory}")

            input_file_path = os.path.join(sim_directory, "input.csv")

            # Create the CSV file from the validated inputs
            logger.info("Processing structured CSV data for Simul8")

            yaml_csv_to_file(inputs, file_path=input_file_path)

            logger.debug("Created input file at: %s", input_file_path)

            # Verify the file was created
            if os.path.exists(input_file_path):
                with open(input_file_path, 'r') as f:
                    content = f.read()
                    logger.debug("File content:\n%s", content)
            else:
                raise Simul8SimulationError(
                    "Failed to create input.csv at: %s", input_file_path)

        except Exception as e:
            logger.error(
                "Failed to create input file: %s", str(e), exc_info=True
            )
            raise Simul8SimulationError("Error creating input file: %s", str(e))

    def _prepare_inputs_to_csv(self, inputs: Optional[Dict[str, Any]]) -> Path:
        """Prepare inputs and write input.csv next to the simulation file.

        This function does NOT fall back to any example or CWD paths.
        It requires valid inputs and a determinable simulation directory
        (either self.actual_file_path or self.sim_path/self.sim_file).
        """
        if not inputs:
            raise Simul8SimulationError(
                "No inputs provided. Simul8 requires structured inputs to generate input.csv."
            )

        validate_csv_structure(inputs)

        if hasattr(self, 'actual_file_path') and getattr(
                self, 'actual_file_path', None):
            sim_dir = Path(self.actual_file_path).parent
        elif self.sim_path and self.sim_file:
            sim_dir = Path(self.sim_path)
        else:
            raise Simul8SimulationError(
                "Could not determine directory for input.csv creation. "
                "Provide 'path' and 'file' when instantiating Simul8Simulator or set 'actual_file_path'."
            )

        if not sim_dir.exists() or not sim_dir.is_dir():
            raise FileNotFoundError(
                f"Simulation directory not found: {sim_dir}")

        input_path = sim_dir / "input.csv"

        # Write CSV using utility
        yaml_csv_to_file(inputs, file_path=str(input_path))

        if not input_path.exists():
            raise Simul8SimulationError(
                f"Failed to create input.csv at: {input_path}")

        return input_path

    def _parse_output_csv(self, output_csv, outputs=None):
        output_path = Path(output_csv)
        if not output_path.exists():
            raise FileNotFoundError(f"Output CSV not found: {output_path}")

        # Determine expected output keys
        desired_outputs = outputs if isinstance(outputs, dict) else {}

        # Read CSV with headers
        with output_path.open('r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)

            # Read headers
            try:
                headers = next(reader)
                headers = [h.strip() for h in headers]
            except StopIteration:
                raise ValueError(f"CSV file is empty: {output_path}")

            # Read first data row
            try:
                values = next(reader, [])
                values = [v.strip() if v.strip() else "0" for v in values]
            except StopIteration:
                values = []

        # Create header to value mapping
        csv_data = {}
        for i, header in enumerate(headers):
            if i < len(values):
                csv_data[header] = values[i] if values[i] else "0"
            else:
                csv_data[header] = "0"

        # Map outputs to CSV data by matching header names to output
        # descriptions
        results = {}
        for key, header_name in desired_outputs.items():
            results[key] = csv_data.get(header_name, "0")

        return results

    def run(self, file_path: Optional[Union[str, Path]] = None,
            inputs: Optional[Dict[str, Any]] = None,
            outputs: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        High-level run: writes inputs CSV, runs Simul8, reads outputs and returns mapped results.
        """
        # Determine sim file path and validate existence
        if file_path is None and self.sim_path and self.sim_file:
            file_path = str(self.sim_path / self.sim_file)
        if file_path is None:
            raise Simul8SimulationError("No simulation file specified")

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Simulation file '{file_path}' not found")

        # Remember the actual sim file path so helper methods write next to it
        self.actual_file_path = str(file_path)
        # also set sim_path and sim_file for other helpers

        # 1. write input CSV
        input_csv = self._prepare_inputs_to_csv(inputs)

        # 2. run engine -> output CSV
        output_csv = self._run_simul8_engine(file_path, input_csv)

        # 3. parse output CSV and return structured results
        results = self._parse_output_csv(output_csv, outputs)
        self.results = results
        # Attempt to clean up temporary files created for this run
        try:
            self._cleanup_temp_files()
        except Exception as e:
            logger.debug("Could not remove temp files after run: %s", e)

        return results

    # _collect_simulation_results removed in favour of _parse_output_csv

    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata about the simulation execution."""
        metadata = {}
        if self.start_time:
            metadata['execution_time'] = time.time() - self.start_time

        if self.s8:
            try:
                metadata['simul8_version'] = self.s8.Version
            except Exception as e:
                logger.warning("Error retrieving Simul8 version: %s", str(e))

        return metadata

    def _cleanup_temp_files(self) -> None:
        """Remove input.csv and OUTPUT CSV files created for the last run.

        This is a best-effort cleanup that will log warnings on failure but
        will not raise exceptions.
        """
        sim_dir = None
        if hasattr(self, 'actual_file_path') and self.actual_file_path:
            sim_dir = Path(self.actual_file_path).parent
        elif self.sim_path:
            sim_dir = Path(self.sim_path)
        else:
            sim_dir = Path(os.getcwd())

        candidates = [sim_dir / 'input.csv', sim_dir / 'OUTPUT.csv']
        for p in candidates:
            try:
                if p.exists():
                    p.unlink()
                    logger.debug("Removed temp file: %s", p)
            except Exception as e:
                logger.warning("Failed to remove temp file %s: %s", p, e)

    def cleanup(self) -> None:
        """Clean up COM resources and temporary files."""
        if self.s8:
            try:
                # Try to quit the application properly
                try:
                    # First try to close any open simulation
                    try:

                        self.s8.Close()
                        logger.debug("Closed Simul8 simulation")
                    except Exception as close_error:
                        logger.debug(
                            "Error closing simulation: %s",
                            str(close_error))

                    time.sleep(5)

                except Exception as quit_error:
                    logger.warning(
                        "Error quitting Simul8 application: %s",
                        str(quit_error))

                finally:
                    try:
                        del self.s8
                        logger.debug("Released Simul8 COM object reference")
                    except Exception as del_error:
                        logger.warning(
                            "Error deleting COM object: %s", str(del_error))

            except Exception as e:
                logger.warning("Error during COM cleanup: %s", str(e))
            finally:
                self.s8 = None
                if hasattr(self, 'events'):
                    self.events = None

        # Uninitialize COM (this should match the CoInitialize call)
        try:
            # Force garbage collection to release any remaining COM references

            gc.collect()
            time.sleep(3)

            pythoncom.CoUninitialize()
            logger.debug("COM uninitialized")
        except Exception as e:
            logger.warning("Error uninitializing COM: %s", str(e))

        # As a last resort, if cleanup seems to have failed, try force killing
        # processes
        try:
            self.force_kill_simul8_processes()
        except Exception as config_error:
            logger.debug(
                "Could not check force cleanup config: %s",
                str(config_error))

    def force_kill_simul8_processes(self) -> None:
        """Force kill any remaining Simul8 processes as a last resort."""
        try:

            # Find and terminate Simul8 processes
            killed_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    # Check for Simul8 executable names (common variations)
                    proc_name = proc.info['name'].lower()
                    if any(s8_name in proc_name for s8_name in [
                           'simul8', 's8.exe', 'simul8.exe']):
                        proc.terminate()
                        killed_processes.append(proc.info['pid'])
                        logger.warning(
                            "Terminated Simul8 process: %s (PID: %s)",
                            proc.info['name'],
                            proc.info['pid'])

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass

            if killed_processes:
                time.sleep(1)  # Give processes time to terminate gracefully

                # Force kill any that didn't terminate
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if proc.info['pid'] in killed_processes:
                            if proc.is_running():
                                proc.kill()
                                logger.warning(
                                    "Force killed Simul8 process PID: %s", proc.info['pid'])
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass

        except ImportError:
            logger.warning(
                "psutil not available - cannot force kill Simul8 processes")
        except Exception as e:
            logger.error("Error force killing Simul8 processes: %s", str(e))
