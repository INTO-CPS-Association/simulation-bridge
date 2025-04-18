function simulation_agent(steps, show_agent)
    % SIMULAZIONE AD AGENTI INTERATTIVA
    % Modificata per l'integrazione con Python
    
    % Variabile globale per controllo esterno
    global sim_running agent_data;
    sim_running = true;
    
    % Parametri di default
    if nargin < 1
        steps = 10;
    end
    if nargin < 2
        show_agent = 1;
    end

    % Inizializzazione agenti
    num_agents = 3;
    positions = zeros(num_agents, 2);  % [x, y] per ogni agente
    velocities = zeros(num_agents, 2); % Velocità degli agenti
    
    % Struttura dati per l'export
    agent_data = struct(...
        'positions', positions, ...
        'velocities', velocities, ...
        'time', 0, ...
        'current_step', 0, ...
        'running', true ...
    );

    % Setup figura
    fig = figure('Name', 'Simulazione Agenti', 'NumberTitle', 'off');
    hold on;
    axis([-10 10 -10 10]);
    grid on;
    title('Simulazione Movimento Agenti');
    xlabel('X');
    ylabel('Y');

    % Inizializzazione grafica
    colors = lines(num_agents);
    h = gobjects(num_agents,1);
    for i = 1:num_agents
        h(i) = plot(positions(i,1), positions(i,2), 'o', ...
            'MarkerSize', 10, 'MarkerFaceColor', colors(i,:), ...
            'DisplayName', sprintf('Agente %d', i));
    end
    legend show;
    
    % Timer per sincronizzazione
    tic;
    
    % Loop principale
    while sim_running
        % Aggiorna stato agenti
        for i = 1:num_agents
            % Movimento casuale con inerzia
            velocities(i,:) = 0.9 * velocities(i,:) + 0.1 * randn(1,2);
            positions(i,:) = positions(i,:) + velocities(i,:);
            
            % Aggiorna grafica
            set(h(i), 'XData', positions(i,1), 'YData', positions(i,2));
        end
        
        % Aggiorna struttura dati
        agent_data.positions = positions;
        agent_data.velocities = velocities;
        agent_data.time = toc;
        agent_data.current_step = agent_data.current_step + 1;
        agent_data.running = sim_running;
        
        % Forza l'aggiornamento del workspace
        assignin('base', 'agent_data', agent_data);
        
        % Pause breve per permettere la lettura da Python
        pause(0.05); 
        
        % Condizione di uscita opzionale
        if agent_data.current_step >= steps
            sim_running = false;
        end
    end
    
    % Output finale
    if show_agent >= 1 && show_agent <= num_agents
        fprintf('\nStato finale Agente %d:\n', show_agent);
        fprintf('Posizione: [%.2f, %.2f]\n', positions(show_agent,1), positions(show_agent,2));
        fprintf('Velocità: [%.2f, %.2f]\n', velocities(show_agent,1), velocities(show_agent,2));
    end
    
    % Chiudi figura
    close(fig);
end