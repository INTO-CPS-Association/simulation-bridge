function simulation_tennis_ball(steps, show_info, use_gui)
    % SIMULATION_TENNIS_BALL simulates the physics of a tennis ball
    % Inputs:
    %   steps - Maximum number of simulation steps (default: 200)
    %   show_info - Display information during simulation (default: true)
    %   use_gui - Use graphical interface (default: false)
    
    global sim_running agent_data;
    sim_running = true;

    if nargin < 1
        steps = 200;
    end
    if nargin < 2
        show_info = true;
    end
    if nargin < 3
        use_gui = false;
    end

    matfile_path = './matfile/';

    % Create directory if it doesn't exist
    if ~exist(matfile_path, 'dir')
        mkdir(matfile_path);
    end
    
    % Remove existing files to avoid conflicts
    if exist(fullfile(matfile_path, 'agent_data.mat'), 'file')
        delete(fullfile(matfile_path, 'agent_data.mat'));
    end
    if exist(fullfile(matfile_path, 'agent_data_tmp.mat'), 'file')
        delete(fullfile(matfile_path, 'agent_data_tmp.mat'));
    end

    g = 9.81;                     % Gravity [m/s^2]
    dt = 0.05;                    % Time interval
    position = [0.6, 0.25, 1.48]; % Initial position (x,y,z) in meters
    velocity = [12, 5, 10];       % Initial velocity (x,y,z) in m/s
    court_length = 24;            % Tennis court length in m
    bounce_damping = 0.7;         % Energy loss on each bounce

    % Initialize data structure
    agent_data = struct(...
        'position', position, ...
        'velocity', velocity, ...
        'time', 0, ...
        'current_step', 0, ...
        'running', true ...
    );
    
    % Assign the structure for debugging
    assignin('base', 'agent_data', agent_data);
    
    % Write initial file
    save(fullfile(matfile_path, 'agent_data.mat'), 'agent_data');
    
    % Setup graphical interface if requested
    if use_gui
        fig = figure('Name', 'Tennis Simulation', 'NumberTitle', 'off');
        hold on;
        axis equal;
        axis([-5 25 -5 5 0 5]);
        grid on;
        view(3);
        title('Tennis Ball Simulation');
        xlabel('X (m)');
        ylabel('Y (m)');
        zlabel('Z (m)');
        h = plot3(position(1), position(2), position(3), 'ro', 'MarkerSize', 8, 'MarkerFaceColor', 'g');
        
        % Draw tennis court
        % Court outline
        rectangle('Position', [0 -5 23.77 10], 'EdgeColor', 'g');
        % Net
        line([11.885 11.885], [-5 5], [0 1.07], 'Color', 'k', 'LineWidth', 2);
    end

    % Start measuring time
    tic;
    step_count = 0;
    
    % Main simulation loop
    while sim_running && step_count < steps
        % Update physics
        velocity(3) = velocity(3) - g * dt;   % Update Z velocity (gravity)
        position = position + velocity * dt;   % Update position

        % Bounce on ground
        if position(3) < 0
            position(3) = 0;
            velocity(3) = -velocity(3) * bounce_damping;
            % Apply some friction on ground contact
            velocity(1) = velocity(1) * 0.95;
            velocity(2) = velocity(2) * 0.95;
        end
        
        % Add some air resistance
        velocity = velocity * 0.99;

        % Bounce on court boundaries (optional)
        if position(2) < -5 || position(2) > 5
            velocity(2) = -velocity(2) * 0.9;
            position(2) = max(min(position(2), 5), -5);
        end
        
        % Tennis net collision
        if position(1) > 11.885-0.1 && position(1) < 11.885+0.1 && position(3) < 1.07
            velocity(1) = -velocity(1) * 0.5;
            position(1) = (position(1) < 11.885) ? 11.885-0.1 : 11.885+0.1;
        end

        % Increment step counter
        step_count = step_count + 1;
        
        % Update data structure
        agent_data.position = position;
        agent_data.velocity = velocity;
        agent_data.time = toc;
        agent_data.current_step = step_count;
        agent_data.running = true;  % Always true during simulation
        
        % Assign to workspace for debugging
        assignin('base', 'agent_data', agent_data);
        
        % Save in the format used in the reference example
        save(fullfile(matfile_path, 'agent_data_tmp.mat'), 'agent_data');
        movefile(fullfile(matfile_path, 'agent_data_tmp.mat'), fullfile(matfile_path, 'agent_data.mat'), 'f');
        
        % Update visualization if GUI is active
        if use_gui
            set(h, 'XData', position(1), 'YData', position(2), 'ZData', position(3));
            drawnow;
        end

        % Show real-time information
        if show_info && mod(step_count, 5) == 0
            fprintf('\n🎾 Real-time ball state (step %d):\n', step_count);
            fprintf('Position: [%.2f, %.2f, %.2f] m\n', position);
            fprintf('Velocity: [%.2f, %.2f, %.2f] m/s\n', velocity);
        end

        % Pause to simulate real-time
        pause(0.05);  
        
        % Debug: always show that we're executing
        if step_count < 10 || mod(step_count, 20) == 0
            fprintf('Executing step: %d, sim_running: %d\n', step_count, sim_running);
        end

        % Stop simulation if steps reached or ball exceeds court
        if position(1) > court_length
            fprintf('Simulation terminated at step %d (ball left court)\n', step_count);
            break;
        end
        
        % Stop if ball velocity is very low (ball at rest)
        if norm(velocity) < 0.5 && position(3) < 0.01
            fprintf('Simulation terminated at step %d (ball stopped)\n', step_count);
            break;
        end
    end

    % Mark simulation as completed
    agent_data.running = false;
    assignin('base', 'agent_data', agent_data);
    save(fullfile(matfile_path, 'agent_data_tmp.mat'), 'agent_data');
    movefile(fullfile(matfile_path, 'agent_data_tmp.mat'), fullfile(matfile_path, 'agent_data.mat'), 'f');

    % Show final information
    if show_info
        fprintf('\n🎾 Final ball state:\n');
        fprintf('Position: [%.2f, %.2f, %.2f] m\n', position);
        fprintf('Velocity: [%.2f, %.2f, %.2f] m/s\n', velocity);
        fprintf('Simulation completed in %d steps (%.2f seconds)\n', step_count, agent_data.time);
    end

    % Close GUI window if present
    if use_gui && exist('fig', 'var') && ishandle(fig)
        close(fig);
    end
end