classdef SimulationWrapperInteractive < handle
    %SIMULATIONWRAPPERINTERACTIVE  TCP wrapper for interactive
    %MATLAB simulations.  Default parameters are taken from a YAML
    %configuration file, but each key can be overridden at construction
    %time with name–value pairs:
    %
    %   w = SimulationWrapperInteractive();                     % defaults
    %   w = SimulationWrapperInteractive("config/dev.yaml");    % custom file
    %   w = SimulationWrapperInteractive([], ...
    %           "tcp.output_port", 6000, "tcp.retry_delay", 2); % overrides

    properties (Access = private)
        out_client      % tcpclient for outgoing data
        in_client       % tcpclient for incoming data
        last_inputs     % last inputs received (struct / array)
        cfg             % configuration struct loaded from YAML
    end

    methods
        %% ----------------------------------------------------------------
        function obj = SimulationWrapperInteractive(cfgFile, varargin)
            % Constructor
            if nargin == 0 || isempty(cfgFile)
                cfgFile = fullfile(fileparts(mfilename("fullpath")), ...
                                   "..", "config", "default.yaml");
            end
            obj.cfg = obj.loadConfig(cfgFile, varargin{:});

            % Shorthand vars
            Host      = obj.cfg.tcp.host;
            outPort      = obj.cfg.tcp.output_port;
            inPort       = obj.cfg.tcp.input_port;
            maxRetries   = obj.cfg.tcp.max_retries;
            retryDelay   = obj.cfg.tcp.retry_delay;

            % Attempt connection with retry policy
            for retry = 1:maxRetries
                try
                    obj.out_client = tcpclient(Host, outPort);
                    obj.in_client  = tcpclient(Host,  inPort);
                    configureTerminator(obj.out_client, "LF");
                    configureTerminator(obj.in_client,  "LF");
                    break;                     % connected
                catch ME
                    if retry == maxRetries
                        rethrow(ME);            % give up
                    end
                    pause(retryDelay);
                end
            end

            % Read first JSON line (blocking)
            firstLine      = readline(obj.out_client);
            obj.last_inputs = jsondecode(firstLine);
        end

        %% ----------------------------------------------------------------
        function inputs = get_input(obj)
            % Return most-recent inputs, refreshing from socket if available
            t0 = tic;
            timeoutLim = obj.cfg.tcp.timeout_limit;

            newData = obj.try_receive();
            while isempty(newData)
                if toc(t0) > timeoutLim
                    disp("⏳ Timeout: No new input data received.");
                    break;
                end
                pause(0.05); % yield CPU a bit
                newData = obj.try_receive();
            end

            if ~isempty(newData)
                obj.last_inputs = newData;
            end
            inputs = obj.last_inputs;
        end

        %% ----------------------------------------------------------------
        function send_output(obj, output_data)
            json_data = jsonencode(output_data);
            writeline(obj.out_client, json_data);
        end

        %% ----------------------------------------------------------------
        function delete(obj)
            % Destructor – close clients safely
            if ~isempty(obj.out_client) && isvalid(obj.out_client)
                delete(obj.out_client);
            end
            if ~isempty(obj.in_client) && isvalid(obj.in_client)
                delete(obj.in_client);
            end
        end
    end  % methods

    methods (Access = private)
        %% ----------------------------------------------------------------
        function data_struct = try_receive(obj)
            % Non-blocking read of a complete JSON line, if any
            data_struct = [];
            while obj.in_client.NumBytesAvailable > 0
                line = readline(obj.in_client);
                disp("📩 Received:");
                disp(line)
                try
                    data_struct = jsondecode(line);
                catch
                    warning("JSON decode failed, skipping line.");
                end
            end
        end

        %% ----------------------------------------------------------------
        function cfg = loadConfig(~, cfgFile, varargin)
            % Load YAML, then apply dotted-key overrides
            raw    = yamlread(cfgFile);   % returns struct
            cfg    = raw;                 % immutable copy

            % Apply overrides
            for k = 1:2:numel(varargin)
                path  = split(varargin{k}, '.');
                val   = varargin{k+1};
                cfg   = SimulationWrapperInteractive.setDeep(cfg, path, val);
            end
        end
    end  % private methods

    methods (Static, Access = private)
        %% ----------------------------------------------------------------
        function s = setDeep(s, path, val)
            % Recursively set a dotted field in struct 's' to 'val'
            if numel(path) == 1
                s.(path{1}) = val;
            else
                field = path{1};
                if ~isfield(s, field) || ~isstruct(s.(field))
                    s.(field) = struct();
                end
                s.(field) = SimulationWrapperInteractive.setDeep( ...
                                s.(field), path(2:end), val);
            end
        end
    end
end
