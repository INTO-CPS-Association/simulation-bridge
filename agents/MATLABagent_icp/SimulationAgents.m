classdef SimulationAgents < SimulationWrapper
    properties (Constant)
        numAgents = 5;      % numero di agenti
        threshold = 100;    % soglia di terminazione per tutti gli agenti
    end
    
    properties
        positions           % vettore delle posizioni correnti
    end
    
    methods
        function initialize(obj)
            % Alloca e azzera le posizioni
            obj.positions = zeros(obj.numAgents,1);
        end
        
        function update(obj, input)
            % input è un vettore almeno di lunghezza numAgents
            % Aggiorna ciascuna posizione sommando la velocità corrispondente
            vel = input(1:obj.numAgents);
            obj.positions = obj.positions + vel;
        end
        
        function output = getOutput(obj)
            % Restituisce il vettore delle posizioni
            % Deve essere lungo esattamente 5, come dichiarato in SimulationWrapper
            output = obj.positions;
        end
        
        function stop = checkTermination(obj)
            % Termina quando **tutti** gli agenti hanno superato la soglia
            stop = all(obj.positions >= obj.threshold);
        end
    end
end
