"""
matlab_simulator.py - MATLAB Engine Interface for Simulations

This module provides a class for interfacing with MATLAB engine to run simulations.
It handles the lifecycle of MATLAB engine sessions, type conversions between Python and MATLAB,
and proper resource management.

Part of the simulation service infrastructure that enables distributed
MATLAB computational workloads.
"""

import os
import time
from pathlib import Path
from typing import Dict, Union, List, Optional, Any, Tuple

import psutil
import matlab.engine

from ..utils.logger import get_logger

# Configure logger
logger = get_logger()


class MatlabSimulationError(Exception):
    """Custom exception for MATLAB simulation errors."""


class MatlabSimulator:
    """
    Manages the lifecycle of a MATLAB simulation with proper resource management,
    error handling and type conversions.
    """

    def __init__(
            self,
            path: str,
            file: str,
            function_name: Optional[str] = None) -> None:
        """
        Initialize a MATLAB simulator.

        Args:
            path: Directory path containing the simulation files
            file: Name of the main simulation file
            function_name: Name of the function to call (defaults to file name without extension)
        """
        self.sim_path: Path = Path(path).resolve()
        self.sim_file: str = file
        self.function_name: str = function_name or os.path.splitext(file)[0]
        self.eng: Optional[matlab.engine.MatlabEngine] = None
        self.start_time: Optional[float] = None
        self._validate()

    def _validate(self) -> None:
        """Validate the simulation path and file."""
        if not self.sim_path.is_dir():
            raise FileNotFoundError(
                f"Simulation directory not found: {self.sim_path}")

        if not (self.sim_path / self.sim_file).exists():
            raise FileNotFoundError(f"Simulation file '{self.sim_file}' not \
                found at {self.sim_path}")

    def start(self) -> None:
        """Start the MATLAB engine and prepare for simulation."""
        logger.debug(
            "Starting MATLAB engine for simulation: %s", self.sim_file)
        try:
            self.start_time = time.time()
            self.eng = matlab.engine.start_matlab()
            self.eng.eval("clear; clc;", nargout=0)
            self.eng.addpath(str(self.sim_path), nargout=0)
            logger.debug("MATLAB engine started successfully")
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Failed to start MATLAB engine: %s", str(e))
            raise MatlabSimulationError(
                f"Failed to start MATLAB engine: {str(e)}") from e

    def run(self, inputs: Dict[str, Any],
            outputs: List[str]) -> Dict[str, Any]:
        """Run the MATLAB simulation and return the results."""
        if not self.eng:
            raise MatlabSimulationError("MATLAB engine is not started")

        try:
            logger.debug("Running simulation %s with inputs: %s",
                         self.function_name, inputs)
            self.eng.eval("clear variables;", nargout=0)
            matlab_args: List[Any] = [
                self._to_matlab(v) for v in inputs.values()]
            result: Union[Any, Tuple[Any, ...]] = self.eng.feval(
                self.function_name, *matlab_args, nargout=len(outputs))

            return self._process_results(result, outputs)

        except Exception as e:  # pylint: disable=broad-except
            msg = f"Simulation error: {str(e)}"
            logger.error(msg, exc_info=True)
            raise MatlabSimulationError(msg) from e

    def _process_results(self,
                         result: Union[Any, Tuple[Any, ...]],
                         outputs: List[str]) -> Dict[str, Any]:
        """Process MATLAB results into Python types."""
        if len(outputs) == 1:
            return {outputs[0]: self._from_matlab(result)}
        return {
            name: self._from_matlab(
                result[i]) for i,
            name in enumerate(outputs)}

    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata about the simulation execution."""
        metadata: Dict[str, Any] = {}
        if self.start_time:
            metadata['execution_time'] = time.time() - self.start_time

        process = psutil.Process(os.getpid())
        metadata['memory_usage'] = process.memory_info().rss / \
            (1024 * 1024)  # MB

        if self.eng:
            try:
                metadata['matlab_version'] = self.eng.eval(
                    "version", nargout=1)
            except Exception as e:
                logger.warning("Error retrieving MATLAB version: %s", str(e))
        return metadata

    @staticmethod
    def _to_matlab(value: Any) -> Any:
        """Convert Python values to MATLAB types."""
        if isinstance(value, (list, tuple)):
            if not value:
                return matlab.double([])
            return matlab.double(
                list(value)
                if isinstance(value[0],
                              (list, tuple))
                else [list(value)])
        if isinstance(value, bool):
            # Special handling for boolean values
            return value
        if isinstance(value, (int, float)):
            return float(value)
        return value

    @staticmethod
    def _from_matlab(value: Any) -> Any:
        """Convert MATLAB types back to Python types."""
        if isinstance(value, matlab.double):
            size = value.size
            if size == (1, 1):
                return float(value[0][0])
            if size[0] == 1 or size[1] == 1:
                return [value[0][i] for i in range(size[1])] \
                    if size[0] == 1 else [value[i][0] for i in range(size[0])]
            return [[value[i][j]
                     for j in range(size[1])] for i in range(size[0])]
        return value

    def close(self) -> None:
        """Close the MATLAB engine and release resources."""
        if self.eng:
            try:
                self.eng.quit()
                logger.debug("MATLAB engine closed successfully")
            except Exception as e:
                logger.warning("Error closing MATLAB engine: %s", str(e))
            finally:
                self.eng = None
