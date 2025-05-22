function InteractiveSimulation()
    % InteractiveSimulation - Example template for interactive MATLAB simulations
    %
    % This template demonstrates how to create an interactive simulation that can
    % receive updated inputs during execution while continuously sending output
    % data to the Python controller.
    
    % 🔌 Initialize the interactive wrapper
    wrapper = InteractiveSimulationWrapper();
    
    % Receive initial inputs from the Python controller
    inputs = wrapper.get_inputs();
    
    % Extract simulation parameters from inputs
    sim_duration = 100;
    if isfield(inputs, 'duration')
        sim_duration = inputs.duration;
    end
    
    time_step = 0.1;
    if isfield(inputs, 'time_step')
        time_step = inputs.time_step;
    end
    
    amplitude = 1.0;
    if isfield(inputs, 'amplitude')
        amplitude = inputs.amplitude;
    end
    
    frequency = 1.0;
    if isfield(inputs, 'frequency')
        frequency = inputs.frequency;
    end
    
    % Initialize output structure
    output_data = struct();
    output_data.step = 0;
    output_data.status = "Simulation initialized";
    output_data.data = struct('time', 0, 'value', 0);
    
    % Send initial output to the Python controller
    wrapper.send_output(output_data);
    
    % Main simulation loop
    for step = 1:sim_duration
        % Check if the simulation should continue running
        if ~wrapper.should_continue_running()
            output_data.status = "Simulation terminated by user";
            wrapper.send_output(output_data);
            break;
        end
        
        % Check for input updates (non-blocking)
        [has_update, new_inputs] = wrapper.check_for_updates();
        
        % If we have new inputs, update our simulation parameters
        if has_update
            if isfield(new_inputs, 'amplitude')
                amplitude = new_inputs.amplitude;
                output_data.status = sprintf("Updated amplitude to %.2f", amplitude);
            end
            
            if isfield(new_inputs, 'frequency')
                frequency = new_inputs.frequency;
                output_data.status = sprintf("Updated frequency to %.2f", frequency);
            end
        else
            output_data.status = "Running";
        end
        
        % Current simulation time
        current_time = step * time_step;
        
        % Example computation: sine wave with current parameters
        current_value = amplitude * sin(2 * pi * frequency * current_time);
        
        % Update output data
        output_data.step = step;
        output_data.data = struct('time', current_time, 'value', current_value, ...
                                 'amplitude', amplitude, 'frequency', frequency);
        
        % Send output to the Python controller
        wrapper.send_output(output_data);
        
        % Simulate computation time
        pause(time_step);
    end
    
    % Final output
    output_data.status = "Simulation completed";
    wrapper.send_output(output_data);
    
    % Clean up
    delete(wrapper);
end