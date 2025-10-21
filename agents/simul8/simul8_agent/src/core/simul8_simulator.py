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
from pathlib import Path
import pythoncom
from win32com import client
from win32com.client.gencache import EnsureDispatch
from typing import Dict, List, Optional, Any, Union, cast

from ..utils.logger import get_logger
from ..utils.csv_parser import yaml_csv_to_file
from ..utils.config_loader import load_config

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

            self.s8 = EnsureDispatch("Simul8.S8Simulation")

            # Set up event handling
            self.events = client.WithEvents(
                self.s8, self._create_event_handler())

            logger.debug("Simul8 engine started successfully")
        except Exception as e:
            logger.error("Failed to start Simul8 engine: %s", str(e))
            self.cleanup()
            raise Simul8SimulationError(
                f"Failed to start Simul8 engine: {
                    str(e)}") from e

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

                # Collect results
                n = 1
                logger.debug(
                    "Total results count: %d",
                    simulation.s8.ResultsCount)
                while n <= simulation.s8.ResultsCount:
                    # try:
                    result = simulation.s8.Results(n)
                    #     simulation.results[result.Name] = result.Value
                    #     logger.debug("Result %d: %s = %s", n, result.Name, result.Value)
                    # except Exception as e:
                    #     logger.error("Error retrieving result %d: %s", n, e)

                    n += 1

                # End the message loop
                simulation.listen_for_messages = False

        return EventHandler

    def run(self, file_path: Optional[str] = None,
            inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.s8 is None:
            self.start()

        # Reset results
        self.results = {}
        self.listen_for_messages = True

        # Store original working directory to restore later
        original_cwd = os.getcwd()

        try:
            # Determine file path - store as instance attribute
            self.actual_file_path = file_path
            if not self.actual_file_path and self.sim_path and self.sim_file:
                self.actual_file_path = str(self.sim_path / self.sim_file)

            if not self.actual_file_path:
                raise Simul8SimulationError("No simulation file specified")

            # Change working directory to simulation file directory
            sim_directory = os.path.dirname(self.actual_file_path)
            logger.debug(f"Original working directory: {original_cwd}")
            logger.debug(f"Actual file path: {self.actual_file_path}")
            logger.debug(f"Sim directory: {sim_directory}")
            os.chdir(sim_directory)
            logger.debug(f"Changed working directory to: {os.getcwd()}")

            logger.debug("Opening simulation file: %s", self.actual_file_path)
            logger.debug("inputs: %s", inputs)

            # Set input parameters if provided
            self._set_simulation_inputs(inputs)

            self.s8.Open(self.actual_file_path)

            while self.listen_for_messages:
                pythoncom.PumpWaitingMessages()

            self._collect_simulation_results()
            return self.results

        except Exception as e:
            logger.error("Simulation error: %s", str(e), exc_info=True)
            raise Simul8SimulationError(f"Simulation error: {str(e)}") from e
        finally:
            # Restore original working directory
            os.chdir(original_cwd)

            # Close the simulation
            pass

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
                # TODO  fix
                "{'columns': ['col1', 'col2'], 'r1': ['val1', 'val2'], ...}"
            )

        logger.info(f"Processing {len(inputs)} input parameters")

        try:
            # Validate that inputs have the correct CSV structure
            from ..utils.csv_parser import validate_csv_structure
            validate_csv_structure(inputs)

            # Determine where the S8 file is located
            sim_directory = None

            if hasattr(self, 'actual_file_path') and self.actual_file_path:
                sim_directory = os.path.dirname(self.actual_file_path)
            elif self.sim_path and self.sim_file:
                sim_directory = str(self.sim_path)
            else:
                # Load config to get simulation path
                try:
                    config = load_config()
                    config_sim_path = config.get('simulation', {}).get('path')
                    if config_sim_path and os.path.exists(config_sim_path):
                        sim_directory = config_sim_path
                    else:
                        # Fallback to examples directory
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        examples_dir = os.path.normpath(os.path.join(
                            current_dir, "..", "..", "docs", "examples"))

                        if os.path.exists(examples_dir):
                            sim_directory = examples_dir
                        else:
                            sim_directory = os.getcwd()
                except Exception as e:
                    logger.warning(f"Could not load config: {e}")
                    # Fallback to examples directory
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    examples_dir = os.path.normpath(os.path.join(
                        current_dir, "..", "..", "docs", "examples"))

                    if os.path.exists(examples_dir):
                        sim_directory = examples_dir
                    else:
                        sim_directory = os.getcwd()

            input_file_path = os.path.join(sim_directory, "input.csv")

            # Create the CSV file from the validated inputs
            logger.info("Processing structured CSV data for Simul8")

            yaml_csv_to_file(inputs, file_path=input_file_path)

            logger.debug(f"Created input file at: {input_file_path}")

            # Verify the file was created
            if os.path.exists(input_file_path):
                with open(input_file_path, 'r') as f:
                    content = f.read()
                    logger.debug(f"File content:\n{content}")
            else:
                raise Simul8SimulationError(
                    f"Failed to create input.csv at: {input_file_path}")

        except Exception as e:
            logger.error(
                f"Failed to create input file: {
                    str(e)}", exc_info=True)
            raise Simul8SimulationError(f"Error creating input file: {str(e)}")

    def _collect_simulation_results(self) -> None:
        """
        Read simulation results from OUTPUTDATA.csv and map to expected output names.
        """
        from ..utils.csv_parser import read_csv_to_dict

        # Look for the output file in multiple locations
        sim_directory = os.path.dirname(self.actual_file_path)
        logger.debug(
            f"Looking for output files. Sim directory: {sim_directory}")
        logger.debug(f"Current working directory: {os.getcwd()}")

        potential_path = os.path.join(sim_directory, "OUTPUT.csv")

        output_file_path = None

        output_file_path = potential_path
        if not os.path.exists(output_file_path):
            logger.warning(f"Output file not found at: {output_file_path}")
            self.results = {"error": "No output file found"}
            return

        try:
            logger.debug(f"Reading results from: {output_file_path}")

            # Read and display the raw file content
            with open(output_file_path, 'r') as f:
                content = f.read()

            # Create output mapping from expected outputs (from YAML)

            # Create mapping from CSV headers to YAML output names
            output_mapping = {}
            if self.expected_outputs:
                # First, get the CSV headers to see what we're working with
                with open(output_file_path, 'r') as f:
                    import csv
                    reader = csv.reader(f)
                    csv_headers = next(reader, [])
                    csv_headers = [header.strip()
                                   for header in csv_headers if header.strip()]

                # Get YAML output names in order
                yaml_output_names = list(self.expected_outputs.keys())

                # Map CSV headers to YAML output names in order
                for i, csv_header in enumerate(csv_headers):
                    if i < len(yaml_output_names):
                        yaml_name = yaml_output_names[i]
                        output_mapping[csv_header] = yaml_name
                    else:
                        output_mapping[csv_header] = csv_header

            else:
                output_mapping = {}
            # Parse the CSV file with header-based approach
            results = read_csv_to_dict(
                output_file_path, output_mapping=output_mapping)

            # Store the parsed results
            if results:
                self.results.update(results)
                logger.debug(
                    f"Collected {
                        len(results)} results from output file")
            else:
                self.results = {"error": "No results parsed from output file"}

        except Exception as e:
            logger.error(f"Failed to read output file: {str(e)}")
            self.results['error'] = f"Error reading results: {str(e)}"

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
                            f"Error closing simulation: {
                                str(close_error)}")

                    time.sleep(0.5)

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
            import gc
            gc.collect()
            time.sleep(0.2)

            pythoncom.CoUninitialize()
            logger.debug("COM uninitialized")
        except Exception as e:
            logger.warning("Error uninitializing COM: %s", str(e))

        # As a last resort, if cleanup seems to have failed, try force killing processes
        # This can be enabled via configuration if needed
        try:
            self.force_kill_simul8_processes()
        except Exception as config_error:
            logger.debug(
                f"Could not check force cleanup config: {
                    str(config_error)}")
            # Optionally, you can uncomment the next line for development/testing:
            # self.force_kill_simul8_processes()

    def force_kill_simul8_processes(self) -> None:
        """Force kill any remaining Simul8 processes as a last resort."""
        try:
            import subprocess
            import psutil

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
                            f"Terminated Simul8 process: {
                                proc.info['name']} (PID: {
                                proc.info['pid']})")
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
                                    f"Force killed Simul8 process PID: {
                                        proc.info['pid']}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass

        except ImportError:
            logger.warning(
                "psutil not available - cannot force kill Simul8 processes")
        except Exception as e:
            logger.error(f"Error force killing Simul8 processes: {str(e)}")
