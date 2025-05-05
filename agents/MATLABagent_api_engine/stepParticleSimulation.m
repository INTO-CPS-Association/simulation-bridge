function [newState, data] = stepParticleSimulation(state, params)
    % Aggiorna posizioni
    domainSize = [10, 10];  % <-- Fisso: 10x10
    newState = state;
    newState.positions = newState.positions + newState.velocities * params.timeStep;
    
    % Rimbalzo sui bordi
    for i = 1:size(newState.positions,1)
        for d = 1:2
            if newState.positions(i,d) < 0 || newState.positions(i,d) > domainSize(d)
                newState.velocities(i,d) = -newState.velocities(i,d);
            end
        end
    end
    
    % Prepara dati di output
    data.positions = newState.positions;
    data.velocities = newState.velocities;
end
