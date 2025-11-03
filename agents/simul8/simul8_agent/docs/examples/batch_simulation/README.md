# Batch Simulation
This simulation is a simple case of the batch simulation,
which the only supported type of simulation for Simul8
It takes 4 inputs, in a the form of arrays, which are translated into a csv file,
as input for the simulation.
The inputs are:

- run_time: 500
- columns: [co2,energy]
- r1: [25, 100]
- r2: [25, 200]

_The format of these input should be read column wise, hence:
 "co2" values are 25 and 25, "energy" values are 100 and 200._

The simulation provides the sum of these as the outputs:

- total_co2: Total CO2
- total_energy: Total Energy

Hence we expect ``total_co2`` = 50, and ``total_energy`` = 300.

## Usage

Before running the simulation, you need to configure the Simul8 Agent
by setting the simulation folder path in the `config.yaml`
file under the simulation section:

```yaml
simulation:
  path: <path_to_simulation_folder>
```

This path should point to the directory `batch-simulation`
containing the simulation files

Once configured, you can initiate the simulation using the API as described below.

The simulation can be initiated via the API by submitting a YAML payload,
a template of which is available in the file `api/simulation.yaml`

```yaml
simulation:
  request_id: simul8_1
  client_id: dt
  simulator: simul8
  type: batch
  file: mysim.s8
  inputs:
    run_time: 500
    columns: [co2, energy]
    r1: [25, 100]
    r2: [25, 200]
  outputs:
    total_co2: Total CO2
    total_energy: Total Energy
```

Use from the client folder, use `use_simul8_agent.py`
with the CLI option `--api-payload` to specify the path to this YAMl file,
and start the client.
