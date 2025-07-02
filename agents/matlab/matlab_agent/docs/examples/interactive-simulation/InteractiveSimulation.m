% InteractiveSimulation.m - Main interactive simulation function
function InteractiveSimulation()
    wrapper = SimulationWrapper();
    disp("🟢 Starting communication loop...");
    while true
        % Receive data from Python (blocking at start, then streaming)
        data_in = wrapper.get_inputs();

        if ~isempty(data_in)
            disp("📥 Input received:");
            disp(data_in);
        end

        % Send output every 50ms (independent of input)
        output = struct("timestamp", posixtime(datetime('now')));
        wrapper.send_output(output);

        pause(0.05);
    end
end
