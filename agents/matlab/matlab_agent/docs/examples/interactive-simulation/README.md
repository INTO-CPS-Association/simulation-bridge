# Interactive Simulation

The `InteractiveSimulation` is a 'Hello world' MATLAB-based simulation that interacts with external clients, processes telemetry data, and returns predicted positions for a moving object. Both input and output are in streaming.
The simulation operates in steps: it receives input, validates it, computes the next position using velocity and time, and sends the result back. This process repeats for up to 100 steps.

Telemetry data must include time (`t`), position (`x`, `y`), and velocity (`vx`, `vy`). The simulation uses the Euler method to predict the next position (`x_next`, `y_next`). If required data is missing or invalid, an error message is returned. After 100 steps, the simulation terminates.

Communication with the MATLAB agent is handled via TCP, using the `SimulationWrapperInteractive` object to manage data exchange.

## Table of Contents

- [Interactive Simulation](#interactive-simulation)
  - [Table of Contents](#table-of-contents)
  - [Usage](#usage)
    - [Stream Source convention](#stream-source-convention)
  - [Simulation Steps and Flow](#simulation-steps-and-flow)

## Usage

Run this simulation interactively with a Python client using the specified API payload.

```yaml
simulation:
  # Unique identifier for this simulation request. This ID is used to track and reference the simulation request.
  request_id: abcdef12345

  # Identifier for the client that is sending the simulation request.
  client_id: dt

  # Specifies the simulator type. In this case, it indicates that the simulation is running in MATLAB.
  simulator: matlab

  # Type of simulation. Here, it indicates that the simulation is "interactive", meaning it involves continuous interaction.
  type: interactive

  # Name of the MATLAB script that will handle the simulation. This script will process the input data and return the output.
  file: InteractiveSimulation.m

  # The inputs section defines the data that the simulation will receive to process.
  inputs:
    # Specifies the RabbitMQ stream URL from which the simulation will receive telemetry data.
    # This is the source for continuous stream data to be processed in the simulation.
    stream_source: "rabbitmq://streaming.inputs.sim123"
    REQUIRED: ["t", "x", "y", "vx", "vy"] # required fields
    PAUSE_IO: 0.01 # pause to avoid spin-lock (s)
    MAX_STEPS: 90 # number of iterations before termination

  # The outputs section defines the structure of the results that will be returned after processing the inputs.
  outputs:
    # Predicted values after the simulation process. These values represent the predicted next positions of the object.
    predicted:
      # Predicted x-coordinate of the object in the next time step.
      x_next: float

      # Predicted y-coordinate of the object in the next time step.
      y_next: float

    # Miscellaneous data that could provide additional context or information about the simulation.
    misc:
      # The Euclidean distance from the origin (0, 0) to the current position of the object.
      # This can be used to measure how far the object has moved from its starting point.
      distance_from_origin: float

      # The timestamp of the output data in epoch seconds. This helps to track when the output was generated.
      timestamp: float # epoch seconds
```

Update `use.yaml` to reference `simulation.yaml` as the payload file and configure the required RabbitMQ credentials.

Then run the batch client:

```bash
python .\use_matlab_agent_interactive.py
```

### Stream Source convention

The convention is to express the stream source as a RabbitMQ URI: the `rabbitmq://` prefix is followed by the actual routing key (or queue name).
When the MATLAB Agent receives the YAML payload, it simply strips the prefix (stream_key = sim["inputs"]["stream_source"].replace("rabbitmq://", "")) and uses the remaining part as the routing key.
In practice, a stream can be specified as `rabbitmq://streaming.inputs.sim123`, where `streaming.inputs.sim123` represents the RabbitMQ queue/topic to publish to or consume from.

> **Note:** The stream_source field in the inputs section is mandatory for interactive simulations. This parameter specifies the RabbitMQ stream from which the simulation will receive real-time input data, and it must be included for the simulation to function correctly.

## Simulation Steps and Flow

1. **Initialization**

   - Initialize `SimulationWrapperInteractive` for TCP communication.
   - Prepare to receive telemetry input.

2. **Main Loop**

   - Process telemetry frames from the Python client.
   - Each frame must include: `t`, `x`, `y`, `vx`, `vy`.

3. **Frame Validation**

   - Check for all required fields.
   - If valid, compute next position using Euler method:
     - `x_next = x + vx * dt`
     - `y_next = y + vy * dt`
     - `dt` is the time difference between current and previous `t`.
   - If invalid, send error message.

4. **Output**

   - Send predicted position and additional info (distance from origin, timestamp) to the client.
   - On error, send error packet.

5. **Completion**
   - After all steps, send a "completed" message.
