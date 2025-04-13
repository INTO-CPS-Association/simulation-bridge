% MATLAB MQTT Interface using Python
% This script interfaces with a Python MQTT client to communicate with an MQTT broker

% Configure Python environment
pyenv('Version', '/Users/marcomelloni/.pyenv/versions/3.11.7/bin/python');

% Ensure that the Python module path is in the Python path
pyPath = '/Users/marcomelloni/Desktop/AU University/Simulator+/matlab';
if count(py.sys.path, pyPath) == 0
    insert(py.sys.path, int32(0), pyPath);
end

% Add current directory to Python path if not present
if count(py.sys.path, '') == 0
    insert(py.sys.path, int32(0), '');
end

% Import the Python module
py.importlib.import_module('mqtt_client');

% Load configuration from the YAML file
config = py.mqtt_client.load_config('config.yml');

% Extract the broker and port from the loaded config
broker = string(config{'mqtt'}{'broker'});
port = double(config{'mqtt'}{'port'});
inputTopic = string(config{'topics'}{'input_topic'});
outputTopic = string(config{'topics'}{'output_topic'});

disp("🟢 Simulation active. Waiting for messages on '" + inputTopic + "'...");

% Main processing loop
while true
    try
        % Receive message via MQTT
        rawMsg = py.mqtt_client.subscribe_and_get_message(inputTopic);
        
        if rawMsg == py.None
            % No message received within timeout
            disp("⏱️ No message received within timeout period");
        else
            % Process received message
            msgStr = string(rawMsg);
            data = jsondecode(msgStr);
            
            % Check if data contains 3 numerical values
            if isfield(data, 'value1') && isfield(data, 'value2') && isfield(data, 'value3')
                % Extract values
                val1 = data.value1;
                val2 = data.value2;
                val3 = data.value3;
                
                disp("📩 Values received: " + val1 + ", " + val2 + ", " + val3);
                
                % Perform calculation
                result = val1 * val2 * val3;
                
                % Simulate processing time
                pause(0.1);
                
                % Create result JSON
                resultJson = jsonencode(struct('product', result));
                
                % Publish the result via MQTT
                disp("📤 Publishing the result...");
                py.mqtt_client.publish_message(outputTopic, resultJson);
                disp("📤 Result published to '" + outputTopic + "': " + resultJson);
            else
                disp("⚠️ Invalid data received: Missing required fields");
            end
        end
    catch err
        % Error handling
        disp("❌ Error: " + err.message);
        pause(5); % Longer pause after an error
    end
    
    % Prevent continuous looping too fast
    pause(1);
end