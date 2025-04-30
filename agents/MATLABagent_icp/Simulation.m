classdef Simulation < SimulationWrapper
    properties
        position
    end
    
    methods
        function initialize(obj)
            obj.position = 0;
        end
        
        function update(obj, input)
            obj.position = obj.position + input(1); % Usa il primo input come velocità
        end
        
        function output = getOutput(obj)
            output = [obj.position; zeros(4,1)]; % Restituisci 5 elementi
        end
        
        function stop = checkTermination(obj)
            stop = obj.position >= 1000;
        end
    end
end