# MATLAB Simulation – Guidelines and Best Practices

## Batch Simulation

A batch simulation is executed by providing a complete set of input parameters at the start. The simulation then runs internally to completion without producing intermediate outputs. Once finished, it returns a final output containing the complete results of the simulation.

This mode is suitable for scenarios where real-time observation is not required and the focus is on analyzing the final state or aggregated outcomes of the simulation.

### Batch Requirements

The simulation logic must reside entirely within the main function, defined at the top level as `simulation()`. This function is responsible for handling both inputs and outputs in the following format:

```matlab
function [output1, output2, output3] = simulation(input1, input2, input3, input4, input5)
  % Simulation logic here
end
```

The order of parameters in the YAML file must align **precisely** with the order of the function arguments. The Simulation Bridge extracts these parameters from the YAML file and passes them directly to the function without any intermediate processing. Each YAML parameter corresponds to a specific function argument, ensuring a direct and automatic binding.

#### Example

Below is an example of a simple simulation function:

```matlab
function [x_f, y_f, z_f] = simulation(x_i, y_i, z_i, v_x, v_y, v_z, t)
  x_f = x_i + v_x * t;
  y_f = y_i + v_y * t;
  z_f = z_i + v_z * t;
end
```

In this example:

- Inputs: `x_i`, `y_i`, `z_i`, `v_x`, `v_y`, `v_z`, `t`
- Outputs: `x_f`, `y_f`, `z_f`

The names of the inputs and outputs can be customized as needed, provided they follow the required function signature.

#### References

For additional guidance, refer to the example files located in the `examples/` folder:

- `simulation_batch_1.m`
- `simulation_batch.m`

These files provide reference implementations that can help in structuring your simulation logic.

#### Notes

No additional constraints are imposed on the implementation. The function should be designed to meet the specific requirements of the simulation scenario.

---

## Streaming Simulation

An Streaming simulation is designed to receive a predefined input configuration at startup and continuously produce real-time outputs during execution. These outputs reflect the internal state of the simulation at each step and are made available to external systems (e.g., The Simulation Bridge) without halting the simulation.

### Streaming Requirements

For this type of simulation, you must use the `SimulationWrapper` class, which should be placed in the same folder as the `Simulation.m` file. The `SimulationWrapper.m` handles the TCP/IP connection and communication with the MATLAB agent script.

The simulation logic must be entirely contained within the main function, defined at the top level as `Simulation()`. This function is responsible for managing both inputs and outputs in the following format:

```matlab
function Simulation()
  % 🔌 Initialize the wrapper
  wrapper = SimulationWrapper();

  % Receive input from the MATLAB agent (via JSON)
  inputs = wrapper.get_inputs();

  % Prepare a dummy output structure (basic example)
  output_data = struct();
  output_data.step = 0;
  output_data.status = "Simulation initialized";

  % Send the output to the MATLAB agent
  wrapper.send_output(output_data);

  % Final cleanup
  delete(wrapper);
end
```

#### References

For additional guidance, refer to the example files located in the `examples/` folder:

- `simulation_streaming.m`

These files provide reference implementations to help you structure your simulation logic.

#### Notes

No additional files are handled. All data is transmitted exclusively through the TCP socket.
