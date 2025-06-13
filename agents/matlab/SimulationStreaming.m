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