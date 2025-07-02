"""In-memory client for running simulations via the bridge."""

import sys
import time
from pathlib import Path
from typing import Dict, Any

import yaml

from simulation_bridge import InMemorySimulation


def load_config(config_path: str = "inmemory_use.yaml") -> Dict[str, Any]:
    """Load YAML configuration file."""
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_path}' not found.")
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"Error parsing YAML file: {exc}")
        sys.exit(1)


class InMemoryClient:
    """Simple client using :class:`InMemorySimulation`."""

    def __init__(self, config: Dict[str, Any]):
        self.yaml_file = config.get("yaml_file", "../simulation.yaml")
        bridge_cfg = config.get("bridge_config")
        self.simulation = InMemorySimulation(bridge_cfg)
        self._completed = False

    def _callback(self, message: Dict[str, Any]) -> None:
        print(f"Received: {message}")
        if message.get("status") == "completed":
            self._completed = True
            self.simulation.stop()

    def run(self) -> None:
        try:
            data = yaml.safe_load(
                Path(
                    self.yaml_file).read_text(
                    encoding="utf-8"))
        except FileNotFoundError:
            print(f"Error: YAML file not found at '{self.yaml_file}'")
            sys.exit(1)
        self.simulation.send(data, self._callback)
        print("Simulation request sent. Waiting for results... (Ctrl+C to quit)")
        try:
            while not self._completed:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.simulation.stop()


def main() -> None:
    config = load_config()
    client = InMemoryClient(config)
    client.run()


if __name__ == "__main__":
    main()
