function Simulation()
    % 🔌 Initialize the wrapper for TCP communication
    wrapper = SimulationWrapper(); 
    inputs = wrapper.get_inputs();
    

    % Extract parameters from the received JSON inputs
    time_step = inputs.time_step;
    num_agents = inputs.num_agents;
    max_steps = inputs.max_steps;
    avoidance_threshold = inputs.avoidance_threshold;
    show_agent_index = inputs.show_agent_index;
    use_gui = inputs.use_gui;


    % Simulation parameters
    positions = rand(num_agents, 2) * 20 - 10;
    velocities = zeros(num_agents, 2);
    current_step = 0;

    % GUI settings
    if use_gui
        fig = figure('Name', 'Simulation Agent', 'NumberTitle', 'off');
        hold on;
        axis([-10 10 -10 10]);
        grid on;
        title('Simulation Agent');
        xlabel('X'); ylabel('Y');
        colors = lines(num_agents);
        h = gobjects(num_agents,1);
        for i = 1:num_agents
            h(i) = plot(positions(i,1), positions(i,2), 'o', ...
                'MarkerSize', 10, 'MarkerFaceColor', colors(i,:));
        end
    end

    % Simulation loop
    while current_step < max_steps
        for i = 1:num_agents
            velocities(i,:) = 0.9 * velocities(i,:) + 0.1 * randn(1,2);
            positions(i,:) = positions(i,:) + velocities(i,:);
            for j = 1:num_agents
                if i ~= j
                    distance = norm(positions(i,:) - positions(j,:));
                    if distance < avoidance_threshold
                        velocities(i,:) = velocities(i,:) + (positions(i,:) - positions(j,:)) * 0.1;
                    end
                end
            end
            if use_gui
                set(h(i), 'XData', positions(i,1), 'YData', positions(i,2));
            end
        end

        % Calculate the minimum distance between agents
        min_dist = inf;
        for i = 1:num_agents
            for j = i+1:num_agents
                d = norm(positions(i,:) - positions(j,:));
                if d < min_dist
                    min_dist = d;
                end
            end
        end

        % Send output to Python
        output_data = struct();
        output_data.step = current_step;
        output_data.agents = positions;
        output_data.distance = min_dist;
        wrapper.send_output(output_data);

        current_step = current_step + 1;
        pause(time_step);
    end

    % Cleanup
    if use_gui
        close(fig);
    end
    delete(wrapper);

    % Final output
    if show_agent_index >= 1 && show_agent_index <= num_agents
        fprintf('\nFinal state of Agent %d:\n', show_agent_index);
        fprintf('Position: [%.2f, %.2f]\n', positions(show_agent_index,1), positions(show_agent_index,2));
        fprintf('Velocity: [%.2f, %.2f]\n', velocities(show_agent_index,1), velocities(show_agent_index,2));
    end
end
