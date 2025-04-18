% simulation.m

function [x_f, y_f, z_f] = simulation(x_i, y_i, z_i, v_x, v_y, v_z, t)
    % Calcola la posizione futura della pallina
    x_f = x_i + v_x * t;
    y_f = y_i + v_y * t;
    z_f = z_i + v_z * t;
end

