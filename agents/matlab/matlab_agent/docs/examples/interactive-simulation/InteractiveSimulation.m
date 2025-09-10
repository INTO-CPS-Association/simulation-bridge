function InteractiveSimulation()
    % INTERACTIVESIMULATION  Interactive demo with frame validation.
    %   It processes valid telemetry (t, x, y, vx, vy) and sends an error packet

    wrapper = SimulationWrapperInteractive();
    init = wrapper.get_initial_inputs();  % handshake parameters

    REQUIRED = init.REQUIRED; % required fields in the input frame
    PAUSE_IO = init.PAUSE_IO; % pause to avoid spin-lock (s)
    MAX_STEPS = init.MAX_STEPS; % number of iterations before termination

    last_input = struct();  % cache of the last valid frame
    last_time  = [];        % timestamp of the last valid frame

    step = 0;               % iteration counter

    %% ───── main loop
    while step < MAX_STEPS
        data_in = wrapper.get_input();  % receive data from the Python client

        % 1️⃣ Frame validation
        disp('📥 Received frame:');
        disp(data_in);  % log the incoming frame

        invalid_reason = "";
        if isempty(data_in)
            invalid_reason = "empty frame";
        elseif ~isstruct(data_in)
            invalid_reason = "not a struct";
        elseif ~all(isfield(data_in, REQUIRED))
            missing = REQUIRED(~isfield(data_in, REQUIRED));
            invalid_reason = "missing fields: " + strjoin(missing, ",");
        end

        % 2️⃣ Always generate an output
        if invalid_reason ~= ""
            disp(['❌ Invalid frame: ', invalid_reason]);
            err_out = struct( ...
                "status", "invalid", ...
                "reason", invalid_reason, ...
                "timestamp", posixtime(datetime("now")) ...
            );
            wrapper.send_output(err_out);
        else
            % 3️⃣ If the frame is valid and new, process it
            if isempty(last_input) || ~isequal(data_in, last_input)
                t  = data_in.t;   x  = data_in.x;   y  = data_in.y;
                vx = data_in.vx;  vy = data_in.vy;

                if isempty(last_time)
                    dt = 0;
                else
                    dt = t - last_time;
                end

                x_next = x + vx * dt;
                y_next = y + vy * dt;

                ok_out = struct( ...
                    "status", "ok", ...
                    "predicted", struct("x_next", x_next, "y_next", y_next), ...
                    "misc", struct( ...
                        "distance_from_origin", hypot(x, y), ...
                        "timestamp", posixtime(datetime("now")) ...
                    ) ...
                );

                disp('📤 Output sent:');
                disp(ok_out);
                wrapper.send_output(ok_out);

                last_input = data_in;
                last_time  = t;
            end
        end

        step = step + 1;
        pause(PAUSE_IO);
    end

    wrapper.send_completed();
end
