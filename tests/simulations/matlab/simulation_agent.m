function simulation_agent(steps, show_agent, use_gui)
    global sim_running agent_data;
    sim_running = true;
    sim_running = true;

    % 🔧 Crea la cartella matfile se non esiste
    if ~exist('matfile', 'dir')
        mkdir('matfile');
    end


    if nargin < 1
        steps = 10;
    end
    if nargin < 2
        show_agent = 1;
    end
    if nargin < 3
        use_gui = false;
    end

    num_agents = 3;
    positions = zeros(num_agents, 2);
    velocities = zeros(num_agents, 2);

    agent_data = struct(...
        'positions', positions, ...
        'velocities', velocities, ...
        'time', 0, ...
        'current_step', 0, ...
        'running', true ...
    );

    if use_gui
        fig = figure('Name', 'Simulazione Agenti', 'NumberTitle', 'off');
        hold on;
        axis([-10 10 -10 10]);
        grid on;
        title('Simulazione Movimento Agenti');
        xlabel('X');
        ylabel('Y');
        colors = lines(num_agents);
        h = gobjects(num_agents,1);
        for i = 1:num_agents
            h(i) = plot(positions(i,1), positions(i,2), 'o', ...
                'MarkerSize', 10, 'MarkerFaceColor', colors(i,:), ...
                'DisplayName', sprintf('Agente %d', i));
        end
        legend show;
    end

    tic;

    while sim_running
        for i = 1:num_agents
            velocities(i,:) = 0.9 * velocities(i,:) + 0.1 * randn(1,2);
            positions(i,:) = positions(i,:) + velocities(i,:);
            if use_gui
                set(h(i), 'XData', positions(i,1), 'YData', positions(i,2));
            end
        end

        agent_data.positions = positions;
        agent_data.velocities = velocities;
        agent_data.time = toc;
        agent_data.current_step = agent_data.current_step + 1;
        agent_data.running = true;

        assignin('base', 'agent_data', agent_data);
        % Salva lo stato su file per Python
        save('matfile/agent_data_tmp.mat', 'agent_data');
        movefile('matfile/agent_data_tmp.mat', 'matfile/agent_data.mat');


        pause(0.1);

        if agent_data.current_step >= steps
            sim_running = false;
        end
    end

    agent_data.running = false;
    assignin('base', 'agent_data', agent_data);

    if show_agent >= 1 && show_agent <= num_agents
        fprintf('\nStato finale Agente %d:\n', show_agent);
        fprintf('Posizione: [%.2f, %.2f]\n', positions(show_agent,1), positions(show_agent,2));
        fprintf('Velocità: [%.2f, %.2f]\n', velocities(show_agent,1), velocities(show_agent,2));
    end

    if use_gui
        close(fig);
    end
end
