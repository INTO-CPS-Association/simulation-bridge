function state = setupParticleSimulation(params)
    % Inizializza lo stato degli agenti
    domainSize = [10, 10];  % <-- Fisso: 10x10
    n = params.numAgents;
    state.positions = rand(n,2) .* domainSize;
    state.velocities = (rand(n,2) - 0.5) * 2 * params.speedLimit;
end
  