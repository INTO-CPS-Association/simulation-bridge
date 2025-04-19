# MATLAB Simulation Agent

This Python script implements an agent that listens for simulation requests from a RabbitMQ queue, runs the requested MATLAB simulation, and sends the results back to a response queue. The agent utilizes `pika` for RabbitMQ messaging and `matlab.engine` for interfacing with MATLAB simulations.

![Matlab](../../images/MATLAB-logo.png)

## Components

### 1. **RabbitMQClient**

- A wrapper around RabbitMQ to manage connections, declare queues, and publish/consume messages.
- It supports:
  - Declaring queues (`declare_queue`)
  - Publishing messages (`publish`)
  - Subscribing to queues and handling incoming messages (`subscribe`, `start_consuming`)

### 2. **MatlabSimulator**

- A class for managing MATLAB simulations.
- It starts a MATLAB engine, loads the specified simulation file, and runs the simulation using the provided inputs.
- The simulator handles:
  - File validation (`_validate`)
  - Starting and closing the MATLAB engine (`start`, `close`)
  - Running the simulation with inputs and fetching the results (`run`)
  - Converting Python values to MATLAB-compatible types and vice versa (`_to_matlab`, `_from_matlab`)

### 3. **MatlabAgent**

- The main agent that listens for incoming simulation requests on the RabbitMQ `queue_1` and sends back results to `queue_2`.
- It handles:
  - Receiving simulation requests (`on_request`)
  - Running the simulation using the `MatlabSimulator` class
  - Publishing the simulation results back to the response queue
- The agent is designed to:
  - Subscribe to the request queue (`queue_1`)
  - Start consuming messages from the queue
  - Process simulation requests, run MATLAB simulations, and send results back

## Workflow

1. **Simulation Request:**

   - The agent listens on the RabbitMQ queue `queue_1` for incoming simulation requests. Each request contains a YAML message with the simulation configuration, including:
     - Path to the simulation file
     - Name of the simulation file
     - Input parameters for the simulation
     - Expected output parameters

2. **MATLAB Simulation:**

   - Upon receiving a request, the agent initializes a `MatlabSimulator` object, validates the simulation file, and runs the MATLAB function with the specified inputs.
   - The simulation results are collected and formatted.

3. **Result Response:**
   - Once the simulation completes, the agent sends the results back to the RabbitMQ queue `queue_2`, where the results can be consumed by other components or agents in the system.

## Requirements

- Python 3.x
- MATLAB API ENGINE for python (for the MATLAB engine interface)
- `pika` library for RabbitMQ interaction
- `pyyaml` library for handling YAML data

## MATLAB Engine API Installation

Ensure that the MATLAB Engine API for Python is installed by following the official installation instructions from MathWorks:

[MATLAB Engine API for Python Installation Instructions](https://www.mathworks.com/help/matlab/matlab-engine-for-python.html)

macbook:
poetry shell
cd /Applications/MATLAB_R2024b.app/extern/engines/python
python -m pip install .
python matlab_agent.py

## Configuration

The agent is configured to connect to a RabbitMQ instance running on `localhost` by default. You can change the host by modifying the `host` argument when initializing the `RabbitMQClient` and `MatlabAgent` classes.

The agent listens on two RabbitMQ queues:

- **Request Queue:** `queue_1`
- **Response Queue:** `queue_2`

### The simulation request should include:

- The **path** to the MATLAB script.
- The **name** of the MATLAB script.
- Input parameters for the simulation.
- Expected output variables.

## Example Request

Here’s an example of a simulation request that can be sent to `queue_1`:

```yaml
simulation:
  name: "Example Simulation"
  path: "/path/to/simulation"
  file: "simulate.m"
  inputs:
    param1: 10
    param2: 5
  outputs:
    result1: "output1"
    result2: "output2"
```

## Error Handling

- **MATLAB Simulation Errors:** If there is an error during the MATLAB simulation, a `MatlabSimulationError` exception is raised.
- **Unexpected Errors:** Any other unexpected errors that occur are caught and logged for troubleshooting.

## Running the Agent

To start the agent, simply run the script with:

```bash
python matlab_agent.py
```

The agent will connect to RabbitMQ and start listening for simulation requests. It will automatically handle incoming messages, execute the corresponding MATLAB simulations, and send back the results.
