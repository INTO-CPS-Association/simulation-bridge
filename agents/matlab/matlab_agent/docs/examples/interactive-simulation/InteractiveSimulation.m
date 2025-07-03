function InteractiveSimulation()
    % INTERACTIVESIMULATION  Interactive demo with frame validation.
    %   It processes valid telemetry (t, x, y, vx, vy) and sends an error packet
    %   if the frame is missing required fields.

    %% ───── configuration
    REQUIRED = ["t", "x", "y", "vx", "vy"];  % required fields
    PAUSE_IO = 0.01;                         % pause to avoid spin-lock (s)

    %% ───── initialization

    wrapper = SimulationWrapperInteractive();
    disp("🟢 InteractiveSimulation started...");

    last_input = struct();  % cache of the last valid frame
    last_time  = [];        % timestamp of the last valid frame

    %% ───── main loop
    while true
        data_in = wrapper.get_input();  % receive data from the Python client

        % 1️⃣ Frame validation
        disp('📥 Received frame:');
        disp(data_in);  % log the incoming frame

        invalid_reason = "";
        if isempty(data_in)
            invalid_reason = "empty frame";  % empty frame
        elseif ~isstruct(data_in)
            invalid_reason = "not a struct";  % not a struct
        elseif ~all(isfield(data_in, REQUIRED))
            missing = REQUIRED(~isfield(data_in, REQUIRED));
            invalid_reason = "missing fields: " + strjoin(missing, ",");
        end

        % 2️⃣ Always generate an output, regardless of frame validity
        if invalid_reason ~= ""
            disp(['❌ Invalid frame: ', invalid_reason]);  % log error
            err_out = struct( ...
                "status", "invalid", ...
                "reason", invalid_reason, ...
                "timestamp", posixtime(datetime("now")) ...
            );
            wrapper.send_output(err_out);  % send error packet
        else
            % 3️⃣ If the frame is valid and new, process it
            if isempty(last_input) || ~isequal(data_in, last_input)
                % Extract variables
                t  = data_in.t;   x  = data_in.x;   y  = data_in.y;
                vx = data_in.vx;  vy = data_in.vy;

                % Δt (Euler)
                if isempty(last_time)
                    dt = 0;  % if there's no last time, set dt to 0
                else
                    dt = t - last_time;  % calculate the time difference
                end

                % Prediction
                x_next = x + vx * dt;
                y_next = y + vy * dt;

                % Build output
                ok_out = struct( ...
                    "status", "ok", ...
                    "predicted", struct("x_next", x_next, "y_next", y_next), ...
                    "misc", struct( ...
                        "distance_from_origin", hypot(x, y), ...
                        "timestamp", posixtime(datetime("now")) ...
                    ) ...
                );

                disp('📤 Output sent:');
                disp(ok_out);  % log the output sent

                % Send the valid output packet
                wrapper.send_output(ok_out);

                % Cache the last frame and time
                last_input = data_in;
                last_time  = t;
            end
        end

        pause(PAUSE_IO);  % pause to avoid continuous loop consumption
    end
end
