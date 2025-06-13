classdef SimulationWrapper < handle
    properties (Access = private)
        tcp_client  % TCP client object for communication with Python
        inputs      % Store the inputs received from Python
    end
    
    methods
        % Constructor for the SimulationWrapper class
        function obj = SimulationWrapper()
            % Default port (modifiable)
            port = 5678;

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
        end
        
        % Method to retrieve the input parameters from the Python server
        function inputs = get_inputs(obj)
            inputs = obj.inputs;  % Return the stored inputs
        end
        
        % Method to send output data to the Python server
        function send_output(obj, output_data)
            % Convert the output data to JSON format
            json_data = jsonencode(output_data);
            % Send the JSON-encoded data to Python server
            writeline(obj.tcp_client, json_data);
        end
        
        % Destructor to clean up the TCP client object when the wrapper is deleted
        function delete(obj)
            % Close the TCP connection by deleting the client object
            delete(obj.tcp_client);
        end
    end
end
