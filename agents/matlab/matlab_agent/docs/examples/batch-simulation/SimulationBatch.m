%{
    Description: Calculates the future position of a ball based on its initial position, velocity, and time.
    Parameters:
        - x_i: Initial x-coordinate of the ball (numeric).
        - y_i: Initial y-coordinate of the ball (numeric).
        - z_i: Initial z-coordinate of the ball (numeric).
        - v_x: Velocity of the ball along the x-axis (numeric).
        - v_y: Velocity of the ball along the y-axis (numeric).
        - v_z: Velocity of the ball along the z-axis (numeric).
        - t: Time duration for which the ball moves (numeric).
    Returns:
        - x_f: Final x-coordinate of the ball (numeric).
        - y_f: Final y-coordinate of the ball (numeric).
        - z_f: Final z-coordinate of the ball (numeric).
%}
% simulation.m

function [x_f, y_f, z_f] = simulation(x_i, y_i, z_i, v_x, v_y, v_z, t)
    x_f = x_i + v_x * t;
    y_f = y_i + v_y * t;
    z_f = z_i + v_z * t;
end

