pyenv('Version', '/Users/marcomelloni/.pyenv/versions/3.11.7/bin/python');

% Ensure that the current folder is in the Python path
pyPath = '/Users/marcomelloni/Desktop/AU University/Simulator+/matlab';
if count(py.sys.path, pyPath) == 0
    insert(py.sys.path, int32(0), pyPath);
end

% Import the Python module
py.importlib.import_module('mqtt_client');

% Add current directory to Python path if not present
if count(py.sys.path, '') == 0
    insert(py.sys.path, int32(0), '');
end

% Load configuration from the YAML file
config = py.mqtt_client.load_config('config.yml');

% Extract the broker and port from the loaded config
broker = string(config{'mqtt'}{'broker'});  % Correct way to access nested dictionary values
port = double(config{'mqtt'}{'port'});     % Convert to a MATLAB number

inputTopic = string(config{'topics'}{'input_topic'}); 
outputTopic = string(config{'topics'}{'output_topic'}); 

disp("🟢 Simulation active. Waiting for messages on '" + inputTopic + "'...");

while true
    try
        % Receive message via MQTT
        rawMsg = py.mqtt_client.subscribe_and_get_message(inputTopic, int32(10)); % 10-second timeout
        
        if rawMsg == py.None
            % No message received
        else
            msgStr = string(rawMsg);
            data = jsondecode(msgStr);  % Decode the received JSON
            
            % Check if data contains 3 numerical values
            if isfield(data, 'value1') && isfield(data, 'value2') && isfield(data, 'value3')
                val1 = data.value1;
                val2 = data.value2;
                val3 = data.value3;
                
                disp("📩 Values received: " + val1 + ", " + val2 + ", " + val3);
                
                % Multiply the values together
                result = val1 * val2 * val3;
                pause(1);  % 2-second pause
                
                % Publish the result via MQTT
                disp("📤 Publishing the result...");
                py.mqtt_client.publish_message(outputTopic, num2str(result));
                disp("📤 Result published to '" + outputTopic + "'");
            else
                disp("⚠️ Invalid data received.");
            end
        end
    catch err
        disp("❌ Error: " + err.message);
    end
    pause(1);  % Prevent continuous looping too fast
end
