classdef SimulationWrapperStreaming < handle
    % SIMULATIONWRAPPERSTREAMING  Wrapper for one-way output (streaming) simulations.
    % Reads default parameters from a YAML file, but any key can be overridden:
    %
    %   w = SimulationWrapperStreaming();                    % defaults
    %   w = SimulationWrapperStreaming("config/dev.yaml");   % custom file
    %   w = SimulationWrapperStreaming([], "tcp.output_port", 6000);

    properties (Access = private)
        tcp_client   % tcpclient for bidirectional stream
        inputs       % first JSON payload from Python
        cfg          % configuration struct
    end

    %% ─────────────────────────────────────────────────────────────────────
    methods
        function obj = SimulationWrapperStreaming(cfgFile, varargin)
            % Constructor: load config, open socket, read first payload
            if nargin == 0 || isempty(cfgFile)
                cfgFile = fullfile(fileparts(mfilename("fullpath")), ...
                                   "..", "config", "default.yaml");
            end
            obj.cfg = obj.loadConfig(cfgFile, varargin{:});

            host        = obj.cfg.tcp.host;
            port        = obj.cfg.tcp.output_port;
            maxRetries  = obj.cfg.tcp.max_retries;
            retryDelay  = obj.cfg.tcp.retry_delay;

            for r = 1:maxRetries
                try
                    obj.tcp_client = tcpclient(host, port);
                    configureTerminator(obj.tcp_client, "LF");
                    break;                                 % success
                catch ME
                    if r == maxRetries
                        rethrow(ME);                       % give up
                    end
                    pause(retryDelay);
                end
            end

            firstLine  = readline(obj.tcp_client);
            obj.inputs = jsondecode(firstLine);
        end

        function inputs = get_inputs(obj)
            inputs = obj.inputs;
        end

        function send_output(obj, output_data)
            writeline(obj.tcp_client, jsonencode(output_data));
        end

        function delete(obj)
            if ~isempty(obj.tcp_client) && isvalid(obj.tcp_client)
                delete(obj.tcp_client);
            end
        end
    end

    %% ─────────────────────────────────────────────────────────────────────
    methods (Access = private)
        function cfg = loadConfig(~, cfgFile, varargin)
            cfg = yamlread(cfgFile);               % struct
            for k = 1:2:numel(varargin)            % dotted-key overrides
                path  = split(varargin{k}, '.');
                val   = varargin{k+1};
                cfg   = SimulationWrapperStreaming.setDeep(cfg, path, val);
            end
        end
    end

    methods (Static, Access = private)
        function s = setDeep(s, path, val)         % recursive helper
            if numel(path) == 1
                s.(path{1}) = val;
            else
                f = path{1};
                if ~isfield(s, f) || ~isstruct(s.(f))
                    s.(f) = struct();
                end
                s.(f) = SimulationWrapperStreaming.setDeep(s.(f), path(2:end), val);
            end
        end
    end
end
