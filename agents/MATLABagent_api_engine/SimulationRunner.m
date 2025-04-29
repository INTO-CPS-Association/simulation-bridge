classdef SimulationRunner < handle
    % Classe generica per eseguire simulazioni con MATLAB da Python
    
    properties (Access = private)
        params
        simulationState
        setupFunction
        stepFunction
        terminationFunction
        startTime
    end
    
    methods
        function obj = SimulationRunner(params, setupFunc, stepFunc, termFunc)
            obj.params = params;
            obj.setupFunction = setupFunc;
            obj.stepFunction = stepFunc;
            obj.terminationFunction = termFunc;
            obj.initializeSimulation();
        end
        
        function initializeSimulation(obj)
            obj.simulationState = feval(obj.setupFunction, obj.params);
            obj.startTime = tic;
        end
        
        function [data, hasTerminated] = step(obj)
            [obj.simulationState, data] = feval(...
                obj.stepFunction, ...
                obj.simulationState, ...
                obj.params ...
            );
            data.elapsedTime = toc(obj.startTime);
            hasTerminated = feval(...
                obj.terminationFunction, ...
                obj.simulationState, ...
                obj.params, ...
                data.elapsedTime ...
            );
        end
        
        function run(obj, callback)
            while true
                [data, hasTerminated] = obj.step();
                feval(callback, data);
                if hasTerminated, break; end
                pause(obj.params.timeStep);
            end
        end
    end
end