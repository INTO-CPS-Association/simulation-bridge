# Streaming Simulation

This example showcases a basic "Hello world" streaming simulation that models the movement of multiple agents in a two-dimensional space. Each agent starts at a random position with zero initial velocity. At every simulation step, their velocities are slightly perturbed by random noise, and positions are updated accordingly, simulating simple dynamic behavior.

The simulation relies on `SimulationWrapper.m` to manage TCP/IP communication with the MATLAB agent, allowing real-time data exchange between the simulation and the client.

## Table of Contents

- [Streaming Simulation](#streaming-simulation)
  - [Table of Contents](#table-of-contents)
  - [Usage](#usage)

## Usage

Before running the simulation, you need to configure the Matlab agent by setting the simulation folder path in the `config.yaml` file under the simulation section:

```yaml
simulation:
  path: <path_to_simulation_folder>
```

This path should point to the directory `streaming-simulation` containing the simulation files

Once configured, you can initiate the simulation using the API as described below.

The simulation can be initiated via the API by submitting a YAML payload, a template of which is available in the file `api/simulation.yaml`

```yaml
simulation:
  request_id: abcdef12345 # Unique identifier for the simulation request
  client_id: dt # ID of the client making the request (e.g., Digital Twin)
  simulator: matlab # Specifies MATLAB as the simulation engine
  type: streaming # Simulation type: 'streaming' means continuous, step-wise execution
  file: SimulationStreaming.m # Name of the MATLAB file to run for the streaming simulation
  inputs:
    time_step: 0.05 # Time interval between simulation steps
    num_agents: 8 # Number of agents to simulate
    max_steps: 200 # Maximum number of simulation steps before termination
    avoidance_threshold: 1 # Minimum allowed distance between agents to avoid collisions
    show_agent_index: 1 # Index of the agent to display details for (e.g., position/velocity)
    use_gui: true # Flag to enable or disable the graphical user interface during simulation
  outputs:
    time: float # Current execution time of the simulation step
    current_step: int # Current step number in the simulation loop
    positions: "[[float, float]]" # Array containing the 2D positions of all agents
    velocities: "[[float, float]]" # Array containing the 2D velocities of all agents
    running: bool # Boolean flag indicating whether the simulation is still running
```

Use the client `use_matlab_agent.py` with the CLI option `--api-payload` to specify the path to this YAML payload file and start the client.
