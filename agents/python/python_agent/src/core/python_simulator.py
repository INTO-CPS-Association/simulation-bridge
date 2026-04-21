"""Python script/program executor used by the Python Agent."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


class PythonSimulationError(Exception):
    """Raised when script/program execution fails."""


class PythonSimulator:
    """Execute scripts/programs with CLI parameters and collect outputs."""

    def __init__(self, timeout: Optional[int] = None) -> None:
        self.timeout = timeout
        self.start_time: Optional[float] = None
        self.last_command: List[str] = []

    def run(
        self,
        file_path: Path | str,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Sequence[str]] = None
    ) -> Dict[str, Any]:
        script_path = Path(file_path)
        if not script_path.is_file():
            raise FileNotFoundError(f"Simulation file '{script_path}' not found")

        self.start_time = time.time()
        self.last_command = self._build_command(script_path, inputs or {})

        try:
            completed = subprocess.run(
                self.last_command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Command timed out after {self.timeout}s") from exc
        except OSError as exc:
            raise PythonSimulationError(f"Failed to execute command: {exc}") from exc

        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()

        if completed.returncode != 0:
            raise PythonSimulationError(
                f"Command exited with code {completed.returncode}. stderr: {stderr}"
            )

        parsed_stdout: Any
        try:
            parsed_stdout = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            parsed_stdout = stdout

        selected_outputs: Any = parsed_stdout
        if outputs and isinstance(parsed_stdout, dict):
            selected_outputs = {key: parsed_stdout.get(key) for key in outputs}

        return {
            "outputs": selected_outputs,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": completed.returncode,
            "command": self.last_command,
        }

    def _build_command(self, script_path: Path, inputs: Dict[str, Any]) -> List[str]:
        command: List[str] = self._base_command(script_path)

        positional = inputs.get("args", [])
        if isinstance(positional, list):
            command.extend(str(arg) for arg in positional)

        for key, value in inputs.items():
            if key == "args":
                continue
            cli_key = key if key.startswith("-") else f"--{key}"

            if isinstance(value, bool):
                if value:
                    command.append(cli_key)
                continue

            if isinstance(value, list):
                for item in value:
                    command.extend([cli_key, str(item)])
                continue

            command.extend([cli_key, str(value)])

        return command

    @staticmethod
    def _base_command(script_path: Path) -> List[str]:
        if script_path.suffix == ".py":
            return [sys.executable, str(script_path)]
        return [str(script_path)]

    def get_metadata(self) -> Dict[str, Any]:
        execution_time = 0.0
        if self.start_time is not None:
            execution_time = time.time() - self.start_time

        return {
            "execution_time": execution_time,
            "python_version": sys.version.split()[0],
            "command": self.last_command,
        }

    def cleanup(self) -> None:
        """No-op for parity with other simulators."""
