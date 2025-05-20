classdef InteractiveSimulationWrapper < handle
    properties (Access = private)
        tcp_client      % TCP client object for communication with Python
        inputs          % Store the initial inputs received from Python
        is_interactive  % Flag indicating if the simulation is running in interactive mode
        is_running      % Flag indicating if the simulation is still running
    end
    
    methods
        % Constructor for the InteractiveSimulationWrapper class
        function obj = InteractiveSimulationWrapper()
            % Default port (modifiable)
            port = 5678;
            
            % Check if interactive mode flag is set
            try
                obj.is_interactive = evalin('base', 'interactive_mode');
            catch
                obj.is_interactive = false;
            end

            % Max retries for connecting to the server
            max_retries = 5;
            retry_delay = 1;  % Delay between retries in seconds

            % Try to connect to the server up to 'max_retries' times
            for retry = 1:max_retries
                try
                    % Create a TCP client object to connect to Python server
                    obj.tcp_client = tcpclient('localhost', port);
                    % Configure the TCP client to use LF as a terminator
                    configureTerminator(obj.tcp_client, "LF");
                    break;  % Exit the loop if the connection is successful
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
            data = readline(obj.tcp_client);
            % Decode the received JSON data and store it as 'inputs'
            obj.inputs = jsondecode(data);
            obj.is_running = true;
        end
        
        % Method to retrieve the initial input parameters
        function inputs = get_inputs(obj)
            inputs = obj.inputs;  % Return the stored inputs
        end
        
        % Method to check if there are new input updates available (non-blocking)
        function [has_update, new_inputs] = check_for_updates(obj)
            has_update = false;
            new_inputs = [];
            
            % Only check for updates in interactive mode
            if ~obj.is_interactive || ~obj.is_running
                return;
            end
            
            % Check if there's data available to read
            bytes_available = obj.tcp_client.BytesAvailable;
            
            if bytes_available > 0
                try
                    % Read the updated inputs
                    data = readline(obj.tcp_client);
                    new_inputs = jsondecode(data);
                    
                    % Check if this is a termination command
                    if isfield(new_inputs, 'command') && strcmp(new_inputs.command, 'terminate')
                        obj.is_running = false;
                        has_update = false;
                        return;
                    end
                    
                    % We have a valid update
                    has_update = true;
                catch ME
                    % If there's an error reading/parsing the data, log it
                    warning('Error reading input update: %s', ME.message);
                end
            end
        end
        
        % Method to send output data to the Python server
        function send_output(obj, output_data)
            % Convert the output data to JSON format
            json_data = jsonencode(output_data);
            % Send the JSON-encoded data to Python server
            writeline(obj.tcp_client, json_data);
        end
        
        % Method to check if the simulation should continue running
        function should_continue = should_continue_running(obj)
            should_continue = obj.is_running;
        end
        
        % Destructor to clean up the TCP client object when the wrapper is deleted
        function delete(obj)
            % Close the TCP connection by deleting the client object
            delete(obj.tcp_client);
        end
    end
end