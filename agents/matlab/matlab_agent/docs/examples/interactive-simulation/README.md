# Interactive Simulation

This example showcases a basic "Hello world" interactive simulation.

The simulation relies on `SimulationWrapperInteractive.m` to manage TCP/IP communication with the MATLAB agent, allowing real-time data exchange between the simulation and the client.

## Table of Contents

- [Interactive Simulation](#interactive-simulation)
  - [Table of Contents](#table-of-contents)
  - [Usage](#usage)

## Usage

Before running the simulation, you need to configure the Matlab agent by setting the simulation folder path in the `config.yaml` file under the simulation section:

```yaml
simulation:
  path: <path_to_simulation_folder>
```

This path should point to the directory `interactive-simulation` containing the simulation files

Once configured, you can initiate the simulation using the API as described below.

The simulation can be initiated via the API by submitting a YAML payload, a template of which is available in the file `api/simulation.yaml`

```yaml
simulation:
  request_id: abcdef12345 # Unique identifier for this simulation request
  client_id: dt # Client identifier for tracking purposes
  simulator: matlab # Specifies MATLAB as the simulation engine
  type: interactive # Indicates this is an interactive simulation type
  file: InteractiveSimulation.m # Main MATLAB file to execute
  inputs:
    stream_source: "rabbitmq://streaming.inputs.sim123" # RabbitMQ stream for input data
  outputs:
    predicted:
      x_next: float # Next predicted X coordinate value
      y_next: float # Next predicted Y coordinate value
    misc:
      distance_from_origin: float # Calculated distance from origin point
      timestamp: float # Simulation timestamp in epoch seconds
```

Use the client `use_matlab_agent_interactive.py` to start the client.
