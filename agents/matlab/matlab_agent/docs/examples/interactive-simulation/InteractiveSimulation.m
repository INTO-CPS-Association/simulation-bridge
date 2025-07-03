function InteractiveSimulation()
    %INTERACTIVESIMULATION  Main loop that reacts only to NEW inputs.
    %   Whenever an incoming input frame differs from the previously
    %   processed one, the function sends an output structure back to the
    %   Python side. Otherwise, it idles until a new input arrives.

    wrapper = SimulationWrapperInteractive();
    disp("🟢 Starting communication loop...");

    last_input = [];  % Cache of the most recently processed input

    while true
        % Retrieve input from Python (blocking with timeout inside wrapper)
        data_in = wrapper.get_input();

        if ~isempty(data_in)
            % React only if the input is different from the last one
            if isempty(last_input) || ~isequal(data_in, last_input)
                disp("📥 New input received:");
                disp(data_in);

                % Build and send the output structure
                output = struct( ...
                    "timestamp", posixtime(datetime("now")), ...
                    "inputEcho", data_in ...  % optional echo of input
                );
                wrapper.send_output(output);

                % Update the cache
                last_input = data_in;
            end
        end

        pause(0.01);  % Small pause to avoid a busy‑wait loop
    end
end
