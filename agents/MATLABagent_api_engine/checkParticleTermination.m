function terminated = checkParticleTermination(state, params, elapsedTime)
    % Termina se supera maxTime o la velocità media è troppo bassa
    vel = state.velocities;
    avgSpeed = mean(sqrt(sum(vel.^2,2)));
    terminated = elapsedTime >= params.maxTime || avgSpeed < params.speedLimit*0.1;
end
