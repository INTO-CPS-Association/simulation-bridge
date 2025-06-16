# Batch Simulation

This example showcases a basic "Hello world" batch simulation that computes the future position of a ball moving in three-dimensional space, given an initial position and constant velocity along each axis.

The input parameters are:

- the initial position of the ball (`x_i`, `y_i`, `z_i`)
- the velocity components (`v_x`, `v_y`, `v_z`)
- the time duration `t` for which the ball moves

The simulation returns the final position (`x_f`, `y_f`, `z_f`) using basic equations of uniform linear motion.  
This is a simple, deterministic model used to test the simulation system with customizable input parameters.

## Table of Contents

- [Batch Simulation](#batch-simulation)
  - [Table of Contents](#table-of-contents)
  - [Usage](#usage)

## Usage

Before running the simulation, you need to configure the Matlab agent by setting the simulation folder path in the `config.yaml` file under the simulation section:

```yaml
simulation:
  path: <path_to_simulation_folder>
```

This path should point to the directory `batch-simulation` containing the simulation files

Once configured, you can initiate the simulation using the API as described below.

The simulation can be initiated via the API by submitting a YAML payload, a template of which is available in the file `api/simulation.yaml`

```yaml
simulation:
  request_id: abcdef12345 # Unique identifier for the simulation request
  client_id: dt # ID of the client making the request (e.g., Digital Twin)
  simulator: matlab # Specifies MATLAB as the simulation engine
  type: batch # Simulation type: 'batch' means a one-time execution, not continuous/streaming
  file: SimulationBatch.m # Name of the MATLAB file to run for the simulation
  inputs:
    x_i: 10 # Initial x-coordinate of the ball
    y_i: 9 # Initial y-coordinate of the ball
    z_i: 0 # Initial z-coordinate of the ball
    v_x: 1 # Velocity along the x-axis
    v_y: 14 # Velocity along the y-axis
    v_z: 3 # Velocity along the z-axis
    t: 10 # Duration of motion (time)
  outputs:
    x_f: Final x position # Output field name for the final x-coordinate
    y_f: Final y position # Output field name for the final y-coordinate
    z_f: Final z position # Output field name for the final z-coordinate
```

Use the client `use_matlab_agent.py` with the CLI option `--api-payload` to specify the path to this YAML payload file and start the client.
