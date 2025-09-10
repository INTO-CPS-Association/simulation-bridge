classdef SimulationWrapperInteractive < handle
    % SIMULATIONWRAPPERINTERACTIVE
    % Wrapper for interactive communication with a Python-based simulation client
    % via TCP. Handles input reception, output transmission, and finalization.

    properties (Access = private)
        out_client   % TCP client for sending data to Python
        in_client    % TCP client for receiving data from Python
        last_inputs  % Cache of the most recent valid input frame
    end

    methods
        % Constructor: Establishes TCP connections to the Python client
        function obj = SimulationWrapperInteractive()
            % Default connection settings
            out_host = 'localhost';
            out_port = 5678;
            in_host = 'localhost';
            in_port = 5679;

            % Retry logic configuration
            max_retries = 5;
            retry_delay = 1;  % in seconds

            % Attempt to connect to input and output ports with retry
            for retry = 1:max_retries
                try
                    obj.out_client = tcpclient(out_host, out_port);
                    obj.in_client  = tcpclient(in_host, in_port);

                    configureTerminator(obj.out_client, "LF");
                    configureTerminator(obj.in_client, "LF");

                    break;  % Exit loop upon successful connection
                catch ME
                    if retry == max_retries
                        rethrow(ME);  % Rethrow error if max retries reached
                    end
                    pause(retry_delay);  % Wait before next retry
                end
            end

            % Read initial configuration/handshake data from Python (JSON format)
            data = readline(obj.out_client);
            obj.last_inputs = jsondecode(data);  % Store parsed input
        end

         % Retrieve the initial handshake inputs
        function inputs = get_initial_inputs(obj)
            inputs = obj.last_inputs;
        end


        % Retrieve the latest input data frame (non-blocking with timeout)
        function inputs = get_input(obj)
            timeout_limit = 2;  % Timeout threshold in seconds
            time_start = tic;

            new_data = obj.try_receive();

            % Retry receiving until timeout is reached
            while isempty(new_data)
                if toc(time_start) > timeout_limit
                    disp('⏳ Timeout: No new input data received for a while.');
                    break;
                end
                new_data = obj.try_receive();
            end

            % Update internal cache if new data was received
            if ~isempty(new_data)
                obj.last_inputs = new_data;
            end

            % Return the most recent available inputs
            inputs = obj.last_inputs;
        end

        % Try to receive a new input frame (non-blocking)
        function data_struct = try_receive(obj)
            data_struct = [];

            % Read available data lines from the input stream
            while obj.in_client.NumBytesAvailable > 0
                line = readline(obj.in_client);
                disp("📩 Received:");
                disp(line)
                try
                    data_struct = jsondecode(line);  % Attempt to parse JSON
                catch
                    warning("JSON decode failed");  % Log failure but continue
                end
            end
        end

        % Send a "simulation completed" packet to Python
        function send_completed(obj)
            completed_packet = struct( ...
                "status", "completed", ...
                "timestamp", posixtime(datetime("now")) ...
            );
            disp("✅ Simulation completed. Sending final packet:");
            disp(completed_packet);

            obj.send_output(completed_packet);
        end

        % Send an output frame to the Python client (encoded as JSON)
        function send_output(obj, output_data)
            json_data = jsonencode(output_data);       % Convert to JSON string
            writeline(obj.out_client, json_data);      % Send via TCP
        end

        % Destructor: Gracefully close the TCP connections
        function delete(obj)
            delete(obj.out_client);
            delete(obj.in_client);
        end
    end
end
