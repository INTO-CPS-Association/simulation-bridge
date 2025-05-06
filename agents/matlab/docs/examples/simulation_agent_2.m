function simulation_dynamic_agents(num_agents, max_steps, avoidance_threshold, show_agent_index, use_gui)
    global sim_running simulation_data;
    sim_running = true;

    % 🔧 Crea la cartella matfile se non esiste
    if ~exist('matfile', 'dir')
        mkdir('matfile');
    end

    % Parametri di simulazione
    positions = rand(num_agents, 2) * 20 - 10;  % Posizioni casuali in uno spazio 20x20
    velocities = zeros(num_agents, 2);  % Velocità iniziali

    % Dati della simulazione
    simulation_data = struct(...
        'positions', positions, ...
        'velocities', velocities, ...
        'time', 0, ...
        'current_step', 0, ...
        'running', true ...
    );

    % Impostazioni GUI (se richiesto)
    if use_gui
        fig = figure('Name', 'Simulazione Agenti Dinamici', 'NumberTitle', 'off');
        hold on;
        axis([-10 10 -10 10]);
        grid on;
        title('Simulazione Agenti Dinamici con Evitamento di Collisioni');
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

    tic;  % Timer per la simulazione

    while sim_running
        for i = 1:num_agents
            % Velocità random con piccole variazioni
            velocities(i,:) = 0.9 * velocities(i,:) + 0.1 * randn(1,2);

            % Movimento dell'agente
            positions(i,:) = positions(i,:) + velocities(i,:);

            % Evita collisioni con altri agenti
            for j = 1:num_agents
                if i ~= j
                    distance = norm(positions(i,:) - positions(j,:));
                    if distance < avoidance_threshold  % Se due agenti sono troppo vicini
                        % Modifica la velocità per evitare la collisione
                        velocities(i,:) = velocities(i,:) + (positions(i,:) - positions(j,:)) * 0.1;
                    end
                end
            end

            % Aggiorna la GUI se necessaria
            if use_gui
                set(h(i), 'XData', positions(i,1), 'YData', positions(i,2));
            end
        end

        % Aggiorna i dati della simulazione
        simulation_data.positions = positions;
        simulation_data.velocities = velocities;
        simulation_data.time = toc;
        simulation_data.current_step = simulation_data.current_step + 1;
        simulation_data.running = true;

        % Salva i dati su file per real-time
        save('matfile/simulation_data_tmp.mat', 'simulation_data');
        movefile('matfile/simulation_data_tmp.mat', 'matfile/simulation_data.mat');

        pause(0.1);  % Pausa tra gli step della simulazione

        % Controlla se raggiungere il numero massimo di step
        if simulation_data.current_step >= max_steps
            sim_running = false;  % Termina la simulazione dopo il numero di step
        end
    end

    simulation_data.running = false;
    assignin('base', 'simulation_data', simulation_data);

    % Mostra lo stato finale dell'agente selezionato
    if show_agent_index >= 1 && show_agent_index <= num_agents
        fprintf('\nStato finale Agente %d:\n', show_agent_index);
        fprintf('Posizione: [%.2f, %.2f]\n', positions(show_agent_index,1), positions(show_agent_index,2));
        fprintf('Velocità: [%.2f, %.2f]\n', velocities(show_agent_index,1), velocities(show_agent_index,2));
    end

    % Chiudi la GUI se utilizzata
    if use_gui
        close(fig);
    end

    % Aggiungi lo stato finale come output
    status = struct('completed', true, 'final_step', simulation_data.current_step);
    assignin('base', 'status', status);
end
