%% UR10e Robot - Joint Space Control with Quintic Trajectory Tracking
% This script demonstrates proportional control of a UR10e robot following
% a smooth quintic (5th-order polynomial) trajectory from start to goal pose.
function [outputs] = simulation(qs, qg, tf, showGui, ts)

    %% ====== DEBUG: PRINT RECEIVED INPUTS ======
    fprintf('\n=== [DEBUG] Inputs received by the simulation ===\n');
    if exist('qs','var'),  disp('qs (start pose):');  disp(qs);  else, disp('qs not provided'); end
    if exist('qg','var'),  disp('qg (goal pose):');   disp(qg);  else, disp('qg not provided'); end
    if exist('tf','var'),  fprintf('tf (duration): %s\n', mat2str(tf)); else, disp('tf not provided'); end
    if exist('ts','var'),  fprintf('ts (time step): %s\n', mat2str(ts)); else, disp('ts not provided'); end
    if exist('showGui','var')
        fprintf('showGui: %s\n', mat2str(showGui));
    else
        disp('showGui not provided');
    end
    fprintf('===============================================\n\n');

    if nargin < 1 || isempty(qs), qs = [0; -pi/2;  pi/2; 0; 0; 0]; end
    if nargin < 2 || isempty(qg), qg = [pi/2;  0;   pi/2; 0; pi; pi]; end
    if nargin < 3 || isempty(tf), tf = 3; end
    if nargin < 4 || isempty(ts), ts = 0.005; end
    if nargin < 5 || isempty(showGui), showGui = true; end

    % Forza vettori colonna
    qs = qs(:);  qg = qg(:);

    % Controlla dimensione
    assert(numel(qs)==6 && numel(qg)==6, 'qs e qg devono avere 6 elementi.');

    % Se i valori suggeriscono gradi, converti in radianti
    if max(abs(qs)) > 2*pi, qs = deg2rad(qs); end
    if max(abs(qg)) > 2*pi, qg = deg2rad(qg); end

    % Valida tempi
    validateattributes(tf, {'numeric'}, {'scalar','real','finite','>',0}, mfilename, 'tf');
    validateattributes(ts, {'numeric'}, {'scalar','real','finite','>',0}, mfilename, 'ts');

    % Converte showGui in logico
    showGui = logical(showGui);

    % Proportional gain for trajectory tracking
    K = 100 * eye(6);

    % Display results with a sampling rate
    sampling_rate = 10;
    
    %% ========== ROBOT SETUP ==========
    
    % Load UR10e robot model
    ur10e = loadrobot("universalUR10e", "DataFormat", "column");
    ur10e.Gravity = [0 0 -9.81];  % Set gravity vector [m/s^2]
    
    %% ========== TRAJECTORY GENERATION ==========
    
    % Generate time vector
    time = 0:ts:tf;
    
    % Initialize desired joint trajectory matrix (6 joints x N time steps)
    Qd = zeros(6, length(time));
    
    % Generate quintic polynomial for each joint
    % Initial and final velocities and accelerations are zero
    for i = 1:6
        % Compute polynomial coefficients for joint i
        A = polynomialfit(qs(i), qg(i), 0, 0, 0, 0, 0, tf, 5);
        
        % Evaluate polynomial at each time step
        Qd(i, :) = polyval(A, time);
        dQd(i, :) = polyval(polyder(A), time);
    end
    
    %% ========== VISUALIZE START AND GOAL POSES ==========
    
    if showGui
        figure;
        show(ur10e, qs);
        title('Start Pose (qs)');
        
        figure;
        show(ur10e, qg);
        title('Goal Pose (qg)');
    end
    
    %% ========== TRAJECTORY TRACKING CONTROL ==========
    
    % Initialize state
    q = qs;                          % Current joint positions
    Qhistory = qs;                   % History of actual positions
    dQhistory = zeros(6, 1);         % History of commanded velocities
    T = 0;                           % Simulation time
    counter = 1;                     % Index for desired trajectory
    
    % Control loop: track desired trajectory using proportional control
    while T <= tf || norm(q - qg) > 1e-5
        
        % Compute tracking error
        e = Qd(:, counter) - q;
        
        % Feedforward + Proportional Control law
        u = dQd(:, counter) + K * e;
        
        % Integrate joint positions (Euler method)
        dq = u;
        q = q + dq * ts;
        
        % Log data
        Qhistory = [Qhistory, q];
        dQhistory = [dQhistory, dq];
        
        % Update time and counter
        T = T + ts;
        counter = counter + 1;
        
        % Clamp counter to last time step
        if counter > length(time)
            counter = length(time);
        end
    end
    
    %% ========== OUTPUT VARIABLES ==========
    
    % Create time vector for simulation
    time_sim = 0:ts:ts*(size(Qhistory, 2) - 1);
    
    % Extend desired trajectory to match simulation length
    Qd_extended = [Qd, repmat(Qd(:, end), 1, length(time_sim) - size(Qd, 2))];
    % Extend desired velocities to match simulation length
    dQd_extended = [dQd, repmat(dQd(:, end), 1, length(time_sim) - size(dQd, 2))];

    % Compute tracking error for each time step
    error_history = zeros(1, length(time_sim));
    for k = 1:length(time_sim)
        error_history(k) = norm(Qhistory(:, k) - Qd_extended(:, k));
    end
    
    % Save final outputs
    outputs.desired_positions = Qd_extended(:, 1:sampling_rate:end);
    outputs.actual_positions = Qhistory(:, 1:sampling_rate:end);
    outputs.time = time_sim(1:sampling_rate:end);
    outputs.velocities = dQhistory;                 % Joint velocities [rad/s] (6 x N)
    outputs.tracking_error = error_history;         % Tracking error norm over time
    outputs.final_error = norm(q - qg);             % Final tracking error [rad]
    outputs.final_position = q;                     % Final joint configuration [rad]
    outputs.desired_velocities = dQd;               % Desired Velocities

    %% ========== RESULTS VISUALIZATION ==========
    
    if showGui
        % Plot joint trajectories
        figure;
        plot(time_sim, Qhistory, 'LineWidth', 1.5);
        hold on;
        
        % Plot desired positions at 10% intervals
        marker_indices = mod(time_sim / tf * 100, 10) == 0;
        scatter(time_sim(marker_indices), Qd_extended(:, marker_indices), ...
                50, 'filled', 'MarkerEdgeColor', 'k');
        
        xlabel('Time [s]');
        ylabel('Joint Position [rad]');
        title('Quintic Trajectory Tracking');
        legend('q_1', 'q_2', 'q_3', 'q_4', 'q_5', 'q_6', 'Location', 'best');
        grid on;
        
        % Plot tracking error over time
        figure;
        plot(time_sim, error_history, 'LineWidth', 1.5, 'Color', 'r');
        xlabel('Time [s]');
        ylabel('Tracking Error (norm) [rad]');
        title('Tracking Error vs Time');
        grid on;

        % Plot joint velocities: commanded vs desired
        figure;
        plot(time_sim, dQhistory, 'LineWidth', 1.5);   % commanded/actual (6 curves)
        hold on;
        plot(time_sim, dQd_extended, '--', 'LineWidth', 1.2);  % desired (dashed)
        xlabel('Time [s]');
        ylabel('Joint Velocity [rad/s]');
        title('Joint Velocities: Commanded vs Desired');
        grid on;
        legend({'\omega_1','\omega_2','\omega_3','\omega_4','\omega_5','\omega_6', ...
                '\omega_{1,d}','\omega_{2,d}','\omega_{3,d}','\omega_{4,d}','\omega_{5,d}','\omega_{6,d}'}, ...
               'Location','bestoutside');
        
        % Animate robot motion
        figure;
        ax = gca;
        for k = 1:10:length(time_sim)  % Subsample for faster animation
            show(ur10e, Qhistory(:, k), "Parent", ax, ...
                 "Visuals", "on", "Collisions", "off", ...
                 "FastUpdate", true, "PreservePlot", false);
            title(sprintf('Robot Motion - t = %.3f s', time_sim(k)));
            drawnow;
        end
    end
end