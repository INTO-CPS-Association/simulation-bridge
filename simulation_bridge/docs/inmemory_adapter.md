# In-Memory Adapter

The In-Memory Adapter enables the Simulation Bridge to operate entirely within a Python process without external message brokers. It provides direct communication between client code and simulation components through callback functions.

The adapter bypasses network protocols (RabbitMQ, MQTT, REST) by implementing signal-based communication using Python's Blinker library. All message routing occurs in-process, eliminating broker dependencies while maintaining the same interface as networked adapters.

## API Reference

#### SimulationBridge

```python
class SimulationBridge:
    def __init__(self, config_path: str | None = None)
    def send(self, message: dict, callback: Callable[[dict], None]) -> None
    def stop() -> None
```

##### Constructor

- `config_path`: YAML configuration file path. If provided, configures bridge protocols and parameters.

##### Methods

- `send(message, callback)`: Submits simulation request. The callback receives result dictionaries as they are published.
- `stop()`: Terminates adapters and disconnects signal handlers. Required to prevent resource leaks.

## Message Format

Requests must follow the standard simulation schema:

```python
{
    "simulation": {
        "request_id": str,     # Unique identifier (required)
        "client_id": str,      # Client identifier
        "simulator": str,      # Target simulator ("matlab", etc.)
        "type": str,          # Execution type ("batch", "streaming")
        "file": str,          # Simulation file path
        "timestamp": str | None, # ISO 8601 timestamp
        "timeout": int | None,   # Max processing time (seconds)
        "inputs": dict,       # Input parameters
        "outputs": dict       # Expected output structure
    }
}
```

> Refer to the [Simulation Bridge User Guide](../../USERGUIDE.md) for detailed message structure and requirements.

## Usage Example

To use the In-Memory Adapter, you must create a `config.yaml` file with in-memory mode enabled.

```yaml
simulation_bridge:
  bridge_id: simulation_bridge # Unique identifier for the bridge
  in_memory_mode: true # Enable in-memory operation
  ... # Additional configuration options
```

Here's a simple example demonstrating how to use the In-Memory Adapter to send a simulation request and handle results:

```python
from simulation_bridge import SimulationBridge  # Import the in-memory adapter
import time  # Import time module for sleep functionality
from pathlib import Path # Import Path for file operations
import yaml # Import YAML for configuration loading

completed = False  # Global flag to track simulation completion

def handle_result(msg):  # Callback function to process simulation results
    global completed  # Access global completion flag
    print("\nReceived:", msg)  # Print received message
    if msg.get("status") == "completed":  # Check if simulation is complete
        completed = True  # Set completion flag

sim = SimulationBridge("config.yaml")  # Create simulation instance with config

data = yaml.safe_load(Path("simulation.yaml").read_text(encoding=YAML_ENCODING)) # Load simulation data from YAML file

sim.send(data, handle_result)  # Register callback function for results

print("Simulation sent. Waiting...")  # Status message
try:  # Begin exception handling block
    while not completed:  # Loop until simulation completes
        time.sleep(0.1)  # Brief pause to prevent busy waiting
finally:  # Cleanup block that always executes
    sim.stop()  # Stop simulation and clean up resources
```

> **Note:** For a more robust and maintainable implementation, consider using the `inmemory_client.py` module included in the repository.
> You can generate it automatically using the CLI:
>
> ```bash
> simulation-bridge --generate-project
> ```
>
> The inmemory folder demonstrates a complete client setup with proper configuration loading, result handling, and lifecycle management.
