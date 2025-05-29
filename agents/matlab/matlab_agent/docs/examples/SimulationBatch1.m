function [x_final, y_final, speed_final, time_elapsed] = simulation(x0, y0, speed0, acceleration, angle_deg, simulation_time)
    % SIMULATION OF 2D CAR MOVEMENT
    % Input:
    %   x0, y0: initial position (m)
    %   speed0: initial speed (m/s)
    %   acceleration: acceleration (m/s^2)
    %   angle_deg: initial direction in degrees (0-360°)
    %   simulation_time: total simulation time (s)
    %
    % Output:
    %   x_final, y_final: final position (m)
    %   speed_final: final speed (m/s)
    %   time_elapsed: actual simulated time (s)

    % Convert angle from degrees to radians
    angle_rad = deg2rad(angle_deg);
    
    % Vector components of the initial velocity
    vx0 = speed0 * cos(angle_rad);
    vy0 = speed0 * sin(angle_rad);
    
    % Components of the acceleration
    ax = acceleration * cos(angle_rad);
    ay = acceleration * sin(angle_rad);
    
    % Calculate actual simulation time (avoid cases with negative acceleration and zero speed)
    if acceleration >= 0
        time_elapsed = simulation_time;
    else
        % Time to stop (v = v0 + a*t => t = -v0/a)
        stop_time = -speed0/acceleration;
        time_elapsed = min(simulation_time, stop_time);
    end
    
    % Equations of uniformly accelerated motion
    x_final = x0 + vx0 * time_elapsed + 0.5 * ax * time_elapsed^2;
    y_final = y0 + vy0 * time_elapsed + 0.5 * ay * time_elapsed^2;
    
    % Final speed
    speed_final = speed0 + acceleration * time_elapsed;
    if speed_final < 0
        speed_final = 0;  % The car cannot move backward in this model
    end
    
    % Debug info (optional)
    fprintf('Simulation completed:\n');
    fprintf('Simulated time: %.2f s\n', time_elapsed);
    fprintf('Final position: (%.2f, %.2f) m\n', x_final, y_final);
    fprintf('Final speed: %.2f m/s\n\n', speed_final);
end
