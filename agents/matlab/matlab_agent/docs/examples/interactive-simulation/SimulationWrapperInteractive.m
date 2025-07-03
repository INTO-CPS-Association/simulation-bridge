
classdef SimulationWrapperInteractive < handle
    properties (Access = private)
        out_client  % TCP client object for outgoing data
        in_client   % TCP client object for incoming data
        last_inputs % Store the last inputs received from Python
    end
    
    methods
        % Constructor for the SimulationWrapperInteractive class
        function obj = SimulationWrapperInteractive()
            % Default host and ports (modifiable)
            out_host = 'localhost';
            out_port = 5678;
            in_host = 'localhost';
            in_port = 5679;
            % Max retries for connecting to the server
            max_retries = 5;
            retry_delay = 1;  % Delay between retries in seconds

            % Try to connect to the server up to 'max_retries' times
            for retry = 1:max_retries
                try
                    % Create a TCP client object to connect to Python server
                    obj.out_client = tcpclient(out_host, out_port);
                    obj.in_client = tcpclient(in_host, in_port);
                    configureTerminator(obj.out_client, "LF");
                    configureTerminator(obj.in_client, "LF");
                    break; % Exit the loop if the connection is successful
                catch ME
                    % If connection fails, retry up to 'max_retries' times
                    if retry == max_retries
                        % If max retries reached, rethrow the exception
                        rethrow(ME);
                    end
                    % Wait before retrying
                    pause(retry_delay);
                end
            end

            % Receive the initial parameters in JSON format from Python
            data = readline(obj.out_client);
            % Decode the received JSON data and store it as 'last_inputs'
            obj.last_inputs = jsondecode(data);
        end

        function data_struct = try_receive(obj)
            % Non-blocking receive function to get data if available
            data_struct = [];
            while obj.in_client.NumBytesAvailable > 0
                line = readline(obj.in_client);
                disp("📩 Received:");
                disp(line)
                try
                    data_struct = jsondecode(line);
                catch
                    warning("JSON decode failed");
                end
            end
        end
        
        % Method to retrieve input parameters from the Python server
        function inputs = get_input(obj)
            % Single method to get input data
            % Reads new streaming data if available, otherwise returns last input

            new_data = obj.try_receive();
            if ~isempty(new_data)
                obj.last_inputs = new_data;
            end
            inputs = obj.last_inputs;  % Return the stored inputs
        end

        % Method to send output data to the Python server
        function send_output(obj, output_data)
            % Convert the output data to JSON format
            json_data = jsonencode(output_data);
            % Send the JSON-encoded data to Python server
            writeline(obj.out_client, json_data);
        end

        % Destructor to clean up the TCP client object when the wrapper is deleted
        function delete(obj)
            % Close the TCP connection by deleting the client object
            delete(obj.out_client);
            delete(obj.in_client);
        end
    end
end