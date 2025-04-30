% simulation.m - Esempio di simulazione che utilizza SimulationRunner con visualizzazione real-time
% e comunicazione con Python
function simulation(params)
    % Se non vengono forniti parametri, usa dei valori di default
    if nargin < 1
        params = struct(...
            'timeStep', 0.1, ...
            'maxTime', 100.0, ...
            'initialPosition', [0, 0], ...
            'initialVelocity', [1, 4], ...
            'gravity', 9.81, ...
            'mass', 1.0, ...
            'logFrequency', 5, ... % Ogni quanti step salvare lo stato
            'port', 12345, ...     % Porta per la comunicazione con Python
            'host', 'localhost' ... % Host per la comunicazione con Python
        );
    end
    
    % Crea un'istanza di SimulationRunner
    runner = SimulationRunner(params);
    
    % Inizializza la simulazione con uno stato personalizzato
    initialState = struct(...
        'position', params.initialPosition, ...
        'velocity', params.initialVelocity, ...
        'acceleration', [0, -params.gravity], ...
        'time', 0.0 ...
    );
    
    state = runner.initializeSimulation(initialState);
    
    % Crea una figura per la visualizzazione locale (opzionale)
    % Poiché ora anche Python può visualizzare i dati
    figure('Name', 'Simulazione in tempo reale', 'NumberTitle', 'off');
    
    % Prepara il grafico per la traiettoria
    subplot(2,1,1);
    trajectoryPlot = plot(state.position(1), state.position(2), 'bo-', 'LineWidth', 2);
    hold on;
    currentPosMarker = plot(state.position(1), state.position(2), 'ro', 'MarkerSize', 8, 'MarkerFaceColor', 'r');
    grid on;
    xlabel('Posizione X');
    ylabel('Posizione Y');
    title('Traiettoria');

    % Inizializza i vettori per memorizzare la storia dei dati
    timeHistory = state.time;
    posXHistory = state.position(1);
    posYHistory = state.position(2);
    
    % Grafico per le velocità
    subplot(2,1,2);
    velocityPlot = plot(state.time, [state.velocity(1), state.velocity(2)], '-', 'LineWidth', 2);
    grid on;
    xlabel('Tempo');
    ylabel('Velocità');
    title('Velocità X e Y');
    legend('Vel X', 'Vel Y');
    
    % Funzione per determinare se la simulazione è terminata
    function terminated = isTerminated(state, params, elapsedTime)
        terminated = (elapsedTime >= params.maxTime);
        
        % Termina anche se la particella colpisce il terreno
        if state.position(2) < 0
            terminated = true;
        end
    end
    
    % Loop principale della simulazione
    while ~runner.checkTermination(@isTerminated)
        % Inizia un nuovo passo di simulazione
        stepInfo = runner.beginStep();
        
        % Accedi ai parametri e allo stato corrente
        dt = params.timeStep;
        position = state.position;
        velocity = state.velocity;
        acceleration = state.acceleration;
        
        % Aggiorna la simulazione (esempio di movimento balistico)
        newPosition = position + velocity * dt + 0.5 * acceleration * dt^2;
        newVelocity = velocity + acceleration * dt;
        
        % Aggiorna lo stato attraverso il runner
        newState = struct(...
            'position', newPosition, ...
            'velocity', newVelocity, ...
            'time', state.time + dt ...
        );
        
        state = runner.updateState(newState);
        
        % Aggiungi il nuovo punto alla storia
        timeHistory(end+1) = state.time;
        posXHistory(end+1) = state.position(1);
        posYHistory(end+1) = state.position(2);
        
        % Aggiorna i grafici
        set(trajectoryPlot, 'XData', posXHistory, 'YData', posYHistory);
        set(currentPosMarker, 'XData', state.position(1), 'YData', state.position(2));
        
        % Aggiorna il grafico delle velocità
        set(velocityPlot(1), 'XData', timeHistory, 'YData', [velocityPlot(1).YData, state.velocity(1)]);
        set(velocityPlot(2), 'XData', timeHistory, 'YData', [velocityPlot(2).YData, state.velocity(2)]);
        
        % Adatta gli assi
        subplot(2,1,1);
        axis tight;
        if state.position(2) < 0
            ylim([min(posYHistory)-1, max(posYHistory)+1]);
        else
            ylim([0, max(posYHistory)+1]);
        end
        
        subplot(2,1,2);
        axis tight;

        
        % Termina il passo
        stepInfo = runner.endStep(stepInfo.stepStartTime);
        
        % Aggiorna la visualizzazione
        drawnow;
        
        % Se la particella colpisce il terreno, modifica la velocità (rimbalzo)
        if state.position(2) < 0
            % Calcola la componente verticale della velocità dopo il rimbalzo
            % (con un coefficiente di restituzione per simulare la perdita di energia)
            coeffRestitution = 0.8;
            newVelocity = state.velocity;
            newVelocity(2) = -state.velocity(2) * coeffRestitution;
            
            % Aggiorna anche la posizione per evitare di rimanere sotto il terreno
            newPosition = state.position;
            newPosition(2) = 0;
            
            % Aggiorna lo stato
            state = runner.updateState(struct(...
                'position', newPosition, ...
                'velocity', newVelocity ...
            ));
            
            % Aggiungi evento di rimbalzo nel log
            runner.logEvent('bounce', struct(...
                'position', newPosition, ...
                'velocity_before', [state.velocity(1), -state.velocity(2)/coeffRestitution], ...
                'velocity_after', newVelocity ...
            ));
            
            % Controlla se la velocità verticale è sufficientemente bassa da considerare ferma
            if abs(state.velocity(2)) < 0.1
                fprintf('La particella si è fermata al suolo\n');
                break;
            end
        end
    end
    
    
end