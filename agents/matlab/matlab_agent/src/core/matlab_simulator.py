"""
matlab_simulator.py - MATLAB Engine Interface for Simulations

This module provides a class for interfacing with MATLAB engine to run simulations.
It handles the lifecycle of MATLAB engine sessions, type conversions between Python and MATLAB,
and proper resource management.

Part of the simulation service infrastructure that enables distributed
MATLAB computational workloads.
"""

import os
import re
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
            function_name: Name of the function to call (defaults to file name without
            extension)
        """
        self.sim_path: Path = Path(path).resolve()
        self.sim_file: str = file
        self.function_name: str = function_name or os.path.splitext(file)[0]
        self.eng: Optional[matlab.engine.MatlabEngine] = None
        self.start_time: Optional[float] = None
        self.function_inputs: List[str] = []
        # Check if the path is a directory and if the file exists
        if not self.sim_path.exists() or not (self.sim_path / self.sim_file).exists():
            error_msg = (
                f"Simulation file '{self.sim_file}' not found in directory '{self.sim_path}'.")
            logger.error(error_msg)
        self._validate()
        self.function_inputs = self._parse_function_inputs()

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
        except Exception as e:  # Catch generic exceptions for compatibility
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
            ordered_values = self._order_input_values(inputs)
            matlab_args: List[Any] = [
                self._to_matlab(v) for v in ordered_values]
            result: Union[Any, Tuple[Any, ...]] = self.eng.feval(
                self.function_name, *matlab_args, nargout=len(outputs))

            return self._process_results(result, outputs)

        except Exception as e:  # Catch generic exceptions for compatibility
            msg = f"Simulation error: {str(e)}"
            logger.error(msg, exc_info=True)
            raise MatlabSimulationError(msg) from e

    def _process_results(self, result, outputs):
        """Convert and structure MATLAB function outputs into a Python dictionary."""
        to_py = self._from_matlab  # Helper for converting MATLAB data to Python types
        # Case MATLAB returned a struct/dictionary -> convert each value
        if isinstance(result, dict):
            return {k: to_py(v) for k, v in result.items()}
        # Case Single named output (not a list or tuple)
        if len(outputs) == 1 and not isinstance(result, (list, tuple)):
            return {outputs[0]: to_py(result)}
        # Case Multiple outputs or unstructured sequence
        seq = result if isinstance(result, (list, tuple)) else [result]
        # Assign output names; fallback to generic names if not provided
        names = outputs or [f"out{i}" for i in range(len(seq))]
        # Convert all MATLAB results to Python and return as dict
        return {n: to_py(v) for n, v in zip(names, seq)}

    def _parse_function_inputs(self) -> List[str]:
        """
        Extract ordered input names from the MATLAB function signature so we can map
        dictionary-based inputs to positional arguments reliably.
        """
        try:
            signature_source = (self.sim_path / self.sim_file).read_text(
                encoding='utf-8', errors='ignore')
        except Exception as exc:  # pragma: no cover - non critical path
            logger.debug("Unable to read simulation file for signature parsing: %s", exc)
            return []

        pattern = re.compile(
            r'function\s+(?:\[[^\]]*\]\s*=\s*)?%s\s*\((.*?)\)' % re.escape(self.function_name),
            re.IGNORECASE | re.DOTALL
        )
        match = pattern.search(signature_source)
        if not match:
            logger.debug(
                "Could not locate signature for function '%s' in '%s'",
                self.function_name,
                self.sim_file
            )
            return []

        arg_string = match.group(1).strip()
        if not arg_string:
            return []

        args = [arg.strip() for arg in arg_string.split(',') if arg.strip()]
        logger.debug("Parsed MATLAB function inputs: %s", args)
        return args

    def _order_input_values(self, inputs: Dict[str, Any]) -> List[Any]:
        """
        Arrange incoming inputs so they match the MATLAB function signature.
        Falls back to the original dictionary order when the signature is unavailable.
        """
        if not self.function_inputs:
            return [inputs[key] for key in inputs]

        ordered_keys = [name for name in self.function_inputs if name in inputs]
        used_keys = set(ordered_keys)
        remaining_keys = [key for key in inputs if key not in used_keys]
        ordered_keys.extend(remaining_keys)
        return [inputs[key] for key in ordered_keys]

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
            except matlab.engine.EngineError as e:
                logger.warning("Error closing MATLAB engine: %s", str(e))
            finally:
                self.eng = None
