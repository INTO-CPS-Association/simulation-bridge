classdef SimulationRunner < handle
    % SimulationRunner - Libreria di supporto per simulazioni MATLAB
    %
    % Fornisce utilità standard per l'esecuzione di simulazioni senza imporre
    % una struttura rigida, permettendo alle simulazioni di controllare il flusso.
    % Supporta la comunicazione con Python tramite socket TCP/IP.
    
    properties
        % Proprietà pubbliche accessibili dalle simulazioni
        params              % Parametri della simulazione
        simulationState     % Stato corrente della simulazione
        elapsedTime         % Tempo trascorso dall'inizio della simulazione
        startTime           % Riferimento al tempo di inizio (tic)
        stepCount           % Numero di passi di simulazione eseguiti
        logs                % Struttura per i log di simulazione
    end
    
    properties (Access = private)
        % Proprietà interne, non accessibili dalle simulazioni
        lastStepDuration    % Durata dell'ultimo passo di simulazione
        isInitialized       % Flag che indica se la simulazione è stata inizializzata
        tcpSocket           % Socket per la comunicazione con Python
        isPythonConnected   % Flag che indica se la connessione con Python è attiva
        port                % Porta di comunicazione
        host                % Host per la comunicazione
    end
    
    methods
        function obj = SimulationRunner(params)
            % Costruttore semplificato che accetta solo i parametri
            obj.params = params;
            obj.isInitialized = false;
            obj.stepCount = 0;
            obj.isPythonConnected = false;
            
            % Impostazioni predefinite per la comunicazione TCP/IP
            if isfield(params, 'port')
                obj.port = params.port;
            else
                obj.port = 12345; % Porta predefinita
            end
            
            if isfield(params, 'host')
                obj.host = params.host;
            else
                obj.host = 'localhost'; % Host predefinito
            end
            
            % Inizializza i logs come struttura con cell array vuoti
            obj.logs = struct();
            obj.logs.events = cell(0,1);  % Cell array vuoto esplicito
            obj.logs.states = cell(0,1);  % Cell array vuoto esplicito
            
            % Inizializza la connessione con Python
            obj.initPythonConnection();
        end
        
        function initPythonConnection(obj)
            % Inizializza la connessione socket con Python
            try
                fprintf('Tentativo di connessione a Python su %s:%d...\n', obj.host, obj.port);
                obj.tcpSocket = tcpip(obj.host, obj.port);
                obj.tcpSocket.OutputBufferSize = 65536; % Buffer più grande per JSON
                obj.tcpSocket.InputBufferSize = 8192;
                fopen(obj.tcpSocket);
                obj.isPythonConnected = true;
                fprintf('Connessione stabilita con Python.\n');
                
                % Invia un messaggio di conferma a Python
                obj.sendToPython('connection_established', struct('status', 'OK'));
            catch exception
                warning('SimulationRunner:ConnectionFailed', ...
                      ['Impossibile connettersi a Python: ', exception.message, ...
                       '. Continuerò senza comunicazione con Python.']);
                obj.isPythonConnected = false;
            end
        end
        
        function disconnectFromPython(obj)
            % Chiude la connessione con Python
            if obj.isPythonConnected
                try
                    % Invia un messaggio di chiusura
                    obj.sendToPython('connection_closing', struct('status', 'closing'));
                    fclose(obj.tcpSocket);
                    delete(obj.tcpSocket);
                    obj.isPythonConnected = false;
                    fprintf('Connessione con Python chiusa correttamente.\n');
                catch exception
                    warning('SimulationRunner:DisconnectionFailed', ...
                          ['Errore durante la chiusura della connessione: ', exception.message]);
                end
            end
        end
        
        function sendToPython(obj, eventType, data)
            % Invia dati a Python tramite socket
            % INPUT:
            %   eventType - Tipo di evento (stringa)
            %   data - Struttura dati da inviare a Python
            
            if ~obj.isPythonConnected
                return;
            end
            
            try
                % Crea oggetto messaggio
                message = struct(...
                    'event', eventType, ...
                    'timestamp', datestr(now, 'yyyy-mm-dd HH:MM:SS.FFF'), ...
                    'data', data);
                
                % Converti in JSON
                jsonStr = jsonencode(message);
                
                % Aggiungi terminatore per aiutare Python a identificare i messaggi
                jsonStr = [jsonStr, '#END#'];
                
                % Invia dati
                fprintf(obj.tcpSocket, '%s', jsonStr);
            catch exception
                warning('SimulationRunner:SendFailed', ...
                      ['Errore nell''invio dei dati a Python: ', exception.message]);
                obj.isPythonConnected = false;
            end
        end
        
        function response = receivePythonCommand(obj, timeout)
            % Riceve un comando da Python con timeout
            % INPUT:
            %   timeout - Tempo massimo di attesa in secondi (opzionale)
            % OUTPUT:
            %   response - Comando ricevuto o struttura vuota se timeout
            
            if nargin < 2
                timeout = 0.01; % Default 10ms
            end
            
            if ~obj.isPythonConnected
                response = struct();
                return;
            end
            
            try
                % Controlla se ci sono dati in arrivo
                bytesAvailable = get(obj.tcpSocket, 'BytesAvailable');
                
                if bytesAvailable > 0
                    % Leggi i dati disponibili
                    data = fread(obj.tcpSocket, bytesAvailable);
                    strData = char(data');
                    
                    % Prova a parsare il JSON
                    try
                        response = jsondecode(strData);
                    catch
                        warning('SimulationRunner:InvalidJSON', 'Ricevuto JSON non valido da Python.');
                        response = struct();
                    end
                else
                    % Non ci sono dati disponibili
                    response = struct();
                end
            catch exception
                warning('SimulationRunner:ReceiveFailed', ...
                      ['Errore nella ricezione dati da Python: ', exception.message]);
                response = struct();
            end
        end
        
        function state = initializeSimulation(obj, initialState)
            % Inizializza la simulazione con uno stato iniziale
            % INPUT:
            %   initialState - Stato iniziale fornito dalla simulazione (opzionale)
            % OUTPUT:
            %   state - Lo stato inizializzato
            
            if nargin < 2 || isempty(initialState)
                obj.simulationState = struct();
            else
                obj.simulationState = initialState;
            end
            
            obj.startTime = tic;
            obj.elapsedTime = 0;
            obj.stepCount = 0;
            obj.isInitialized = true;
            
            state = obj.simulationState;
            
            % Log dell'inizializzazione
            obj.logEvent('simulation_initialized');
            
            % Notifica Python
            obj.sendToPython('simulation_initialized', struct(...
                'state', state, ...
                'params', obj.params));
        end
        
        function state = updateState(obj, newState)
            % Aggiorna lo stato della simulazione
            % INPUT:
            %   newState - Nuovo stato o modifiche allo stato
            % OUTPUT:
            %   state - Lo stato aggiornato
            
            if ~obj.isInitialized
                error('SimulationRunner:NotInitialized', ...
                      'Simulazione non inizializzata. Chiamare initializeSimulation prima.');
            end
            
            if isstruct(newState)
                % Aggiorna solo i campi specificati in newState
                fields = fieldnames(newState);
                for i = 1:length(fields)
                    obj.simulationState.(fields{i}) = newState.(fields{i});
                end
            else
                % Sostituisce completamente lo stato
                obj.simulationState = newState;
            end
            
            state = obj.simulationState;
            
            % Invia aggiornamento di stato a Python se connesso
            obj.sendToPython('state_updated', struct(...
                'stepCount', obj.stepCount, ...
                'elapsedTime', obj.elapsedTime, ...
                'state', state));
        end
        
        function elapsedTime = updateTime(obj)
            % Aggiorna il tempo trascorso dall'inizio della simulazione
            % OUTPUT:
            %   elapsedTime - Tempo trascorso in secondi
            
            if ~obj.isInitialized
                error('SimulationRunner:NotInitialized', ...
                      'Simulazione non inizializzata. Chiamare initializeSimulation prima.');
            end
            
            obj.elapsedTime = toc(obj.startTime);
            elapsedTime = obj.elapsedTime;
        end
        
        function stepInfo = beginStep(obj)
            % Inizia un nuovo passo di simulazione
            % OUTPUT:
            %   stepInfo - Informazioni sul passo corrente
            
            if ~obj.isInitialized
                error('SimulationRunner:NotInitialized', ...
                      'Simulazione non inizializzata. Chiamare initializeSimulation prima.');
            end
            
            obj.stepCount = obj.stepCount + 1;
            stepStartTime = tic;
            
            stepInfo = struct(...
                'stepNumber', obj.stepCount, ...
                'elapsedTime', obj.updateTime(), ...
                'stepStartTime', stepStartTime);
            
            % Notifica Python dell'inizio del passo
            obj.sendToPython('step_started', stepInfo);
            
            % Controlla comandi da Python prima di eseguire il passo
            cmd = obj.receivePythonCommand();
            if ~isempty(cmd) && isfield(cmd, 'command')
                % Processa i comandi da Python se necessario
                obj.processPythonCommand(cmd);
            end
        end
        
        function stepInfo = endStep(obj, stepStartTime)
            % Finalizza un passo di simulazione e calcola la durata
            % INPUT:
            %   stepStartTime - Riferimento temporale dell'inizio del passo
            % OUTPUT:
            %   stepInfo - Informazioni sul passo completato
            
            if ~obj.isInitialized
                error('SimulationRunner:NotInitialized', ...
                      'Simulazione non inizializzata. Chiamare initializeSimulation prima.');
            end
            
            obj.lastStepDuration = toc(stepStartTime);
            obj.updateTime();
            
            stepInfo = struct(...
                'stepNumber', obj.stepCount, ...
                'elapsedTime', obj.elapsedTime, ...
                'stepDuration', obj.lastStepDuration);
            
            % Log del completamento del passo
            obj.logEvent('step_completed', stepInfo);
            
            % Notifica Python del completamento del passo
            obj.sendToPython('step_completed', stepInfo);
        end
        
        function processPythonCommand(obj, cmd)
            % Elabora un comando ricevuto da Python
            % INPUT:
            %   cmd - Struttura del comando ricevuto
            
            if ~isfield(cmd, 'command')
                return;
            end
            
            switch cmd.command
                case 'pause'
                    % Implementazione della pausa se necessario
                    fprintf('Comando pausa ricevuto da Python\n');
                    obj.logEvent('python_command_pause');
                    
                case 'resume'
                    % Implementazione del resume se necessario
                    fprintf('Comando resume ricevuto da Python\n');
                    obj.logEvent('python_command_resume');
                    
                case 'stop'
                    % Implementazione dello stop se necessario
                    fprintf('Comando stop ricevuto da Python\n');
                    obj.logEvent('python_command_stop');
                    
                case 'update_params'
                    % Aggiornamento parametri se forniti
                    if isfield(cmd, 'params') && isstruct(cmd.params)
                        fields = fieldnames(cmd.params);
                        for i = 1:length(fields)
                            obj.params.(fields{i}) = cmd.params.(fields{i});
                        end
                        fprintf('Parametri aggiornati da Python\n');
                        obj.logEvent('python_command_update_params');
                    end
                    
                otherwise
                    fprintf('Comando sconosciuto ricevuto da Python: %s\n', cmd.command);
            end
        end
        
        function logEvent(obj, eventName, eventData)
            % Registra un evento nei log della simulazione
            % INPUT:
            %   eventName - Nome dell'evento (stringa)
            %   eventData - Dati associati all'evento (opzionale)
            
            if nargin < 3
                eventData = struct();
            end
            
            event = struct(...
                'name', eventName, ...
                'time', obj.elapsedTime, ...
                'stepCount', obj.stepCount, ...
                'data', eventData);
            
            % Aggiunge l'evento al log
            obj.logs.events{end+1} = event;
            
            % Invia evento a Python
            obj.sendToPython('log_event', event);
        end
        
        function logState(obj, stateName)
            % Salva lo stato corrente nei log
            % INPUT:
            %   stateName - Identificatore per lo stato (opzionale)
            
            if nargin < 2
                stateName = sprintf('state_%d', obj.stepCount);
            end
            
            stateSnapshot = struct(...
                'name', stateName, ...
                'time', obj.elapsedTime, ...
                'stepCount', obj.stepCount, ...
                'state', obj.simulationState);
            
            % Aggiunge lo stato al log
            obj.logs.states{end+1} = stateSnapshot;
            
            % Invia log stato a Python
            obj.sendToPython('log_state', stateSnapshot);
        end
        
        function saveLogs(obj, filename)
            % Salva i log su file
            % INPUT:
            %   filename - Nome del file (opzionale)
            
       
            
            % Notifica Python
            obj.sendToPython('logs_saved', struct('filename', filename));
        end
        
        function pauseSimulation(obj, duration)
            % Mette in pausa l'esecuzione della simulazione
            % INPUT:
            %   duration - Durata della pausa in secondi (opzionale)
            
            if nargin < 2
                if isfield(obj.params, 'timeStep')
                    duration = obj.params.timeStep;
                else
                    duration = 0.01; % Default
                end
            end
            
            % Controlla comandi da Python durante la pausa
            startTime = tic;
            while toc(startTime) < duration
                cmd = obj.receivePythonCommand(0.01);
                if ~isempty(cmd) && isfield(cmd, 'command')
                    obj.processPythonCommand(cmd);
                end
                pause(0.01); % Rilascia la CPU per un po'
            end
        end
        
        function result = checkTermination(obj, terminationCondition)
            % Verifica se la simulazione deve terminare
            % INPUT:
            %   terminationCondition - Funzione handle che accetta state e params
            %                         e restituisce true/false
            % OUTPUT:
            %   result - true se la simulazione deve terminare
            
            if isa(terminationCondition, 'function_handle')
                result = terminationCondition(obj.simulationState, obj.params, obj.elapsedTime);
            elseif islogical(terminationCondition)
                result = terminationCondition;
            else
                error('SimulationRunner:InvalidTermination', ...
                      'La condizione di terminazione deve essere un function handle o un valore logico.');
            end
            
            if result
                obj.logEvent('simulation_terminated');
                obj.sendToPython('simulation_terminated', struct(...
                    'elapsedTime', obj.elapsedTime, ...
                    'stepCount', obj.stepCount, ...
                    'finalState', obj.simulationState));
                
                % Chiudi la connessione alla fine della simulazione
                obj.disconnectFromPython();
            end
        end
        
        function delete(obj)
            % Distruttore per pulire le risorse
            if obj.isPythonConnected
                obj.disconnectFromPython();
            end
        end
    end
end