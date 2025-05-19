%% Inizializzazione parametri globali
dt = 0.1;              % Time step in secondi
roadRadius = 800;      % Raggio del circuito urbano in metri
numIntersections = 6;  % Numero di incroci/strisce pedonali
carSpeedMax = 3;     % m/s (~54 km/h)
carAccel = 0.2;        % Accelerazione massima (m/s²)
carDecel = 0.4;        % Decelerazione massima (m/s²)
safetyMargin = 5;      % Margine di sicurezza aggiuntivo (metri)

%% 1. Definizione topologia urbana
intersectionAngles = linspace(0, 2*pi, numIntersections+1);
intersectionAngles(end) = [];
global trafficLights;
trafficLights = struct(...
    'position', num2cell(intersectionAngles),...
    'state', repmat({'green'}, 1, numIntersections),...
    'timer', num2cell(randi([500, 600], 1, numIntersections)),...
    'pedestrianRequest', num2cell(false(1, numIntersections)));


if ~exist('matfile', 'dir')
    mkdir('matfile');
end

%% 2. Inizializzazione veicolo autonomo
car = struct(...
    'theta', 0, ...
    'speed', 0, ...
    'nextLight', 1, ...
    'stopped', false);

%% 3. Interfaccia grafica unica
mainFig = figure('Position', [100 100 1200 600]);
tiledlayout(mainFig,1,2);

% Vista città
axSim = nexttile;
hold(axSim, 'on');
axis(axSim, 'equal');
xlim(axSim, [-roadRadius*1.2 roadRadius*1.2]);
ylim(axSim, [-roadRadius*1.2 roadRadius*1.2]);
title(axSim, 'Simulazione Smart City - Traffico Urbano');
xlabel(axSim, 'X (m)');
ylabel(axSim, 'Y (m)');

theta = linspace(0, 2*pi, 100);
plot(axSim, roadRadius*cos(theta), roadRadius*sin(theta), 'k-', 'LineWidth', 2);

for i = 1:numIntersections
    angle = intersectionAngles(i);
    plot(axSim, [roadRadius*0.9*cos(angle), roadRadius*1.1*cos(angle)],...
         [roadRadius*0.9*sin(angle), roadRadius*1.1*sin(angle)],...
         'k--', 'LineWidth', 1.5);
end

carPlot = plot(axSim, 0, 0, 'bo', 'MarkerSize', 12, 'MarkerFaceColor', 'b');
lightPlots = gobjects(numIntersections,1);
for i = 1:numIntersections
    [x,y] = pol2cart(trafficLights(i).position, roadRadius);
    lightPlots(i) = plot(axSim, x, y, 's', 'MarkerSize', 18, 'LineWidth', 3,...
                         'MarkerEdgeColor', [0 0.7 0]);
end

% Pannello di controllo
controlPanel = nexttile;
title(controlPanel, 'Controllo Semafori');
axis(controlPanel, 'off');

lightPopups = gobjects(numIntersections,1);
for i = 1:numIntersections
    uicontrol(mainFig, 'Style','text','Units','normalized',...
        'Position',[0.72 0.9 - (i-1)*0.12 0.05 0.04],...
        'String',['S' num2str(i)], 'FontWeight','bold');

    lightPopups(i) = uicontrol(mainFig, 'Style','popupmenu',...
        'Units','normalized',...
        'Position',[0.77 0.9 - (i-1)*0.12 0.1 0.04],...
        'String',{'green','yellow','red'},...
        'Callback',@(src,~) changeLightState(src,i));
end

% Callback cambio stato semafori
function changeLightState(src, lightIndex)
    global trafficLights;
    newState = src.String{src.Value};
    trafficLights(lightIndex).state = newState;

    switch newState
        case 'green'
            trafficLights(lightIndex).timer = randi([200,300]);
        case 'yellow'
            trafficLights(lightIndex).timer = 300;
        case 'red'
            trafficLights(lightIndex).timer = 350;
            trafficLights(lightIndex).pedestrianRequest = false;
    end
end

%% 4. Inizializzazione logging
log = struct();
log.time = [];
log.carPos = [];
log.carSpeed = [];
log.lightStates = {};
logIndex = 1;
agent_data = struct();


%% 5. Loop simulazione
t = 0;
while ishandle(mainFig)
    %% A. Aggiorna semafori (solo aggiornamento visivo e sync GUI)
    for i = 1:numIntersections
        trafficLights(i).timer = trafficLights(i).timer - dt;

        currentState = trafficLights(i).state;
        set(lightPopups(i), 'Value', find(strcmp(lightPopups(i).String, currentState)));

        switch currentState
            case 'green'
                set(lightPlots(i), 'MarkerEdgeColor', [0 0.7 0]);
            case 'yellow'
                set(lightPlots(i), 'MarkerEdgeColor', [1 0.8 0]);
            case 'red'
                set(lightPlots(i), 'MarkerEdgeColor', [1 0 0]);
        end
    end

    %% B. Controllo veicolo
    nextLightID = car.nextLight;
    angleToNextLight = trafficLights(nextLightID).position - car.theta;
    if angleToNextLight < 0
        angleToNextLight = angleToNextLight + 2*pi;
    end
    distanceToLight = angleToNextLight * roadRadius;

    stoppingDistance = car.speed^2 / (2*carDecel) + safetyMargin;

    nextLightState = trafficLights(nextLightID).state;
    mustStop = strcmp(nextLightState, 'red') || (strcmp(nextLightState, 'yellow') && distanceToLight < stoppingDistance);

    if mustStop
        targetSpeed = 0;
        car.stopped = true;
    else
        targetSpeed = carSpeedMax;
        car.stopped = false;
    end

    if car.speed < targetSpeed
        car.speed = min(car.speed + carAccel*dt, targetSpeed);
    else
        car.speed = max(car.speed - carDecel*dt, targetSpeed);
    end

    car.theta = mod(car.theta + car.speed/roadRadius * dt, 2*pi);
    [~, car.nextLight] = min(abs([trafficLights.position] - car.theta));

    %% C. Aggiorna visualizzazione
    [x_car, y_car] = pol2cart(car.theta, roadRadius);
    set(carPlot, 'XData', x_car, 'YData', y_car);
    drawnow limitrate;

    %% D. Logging dati
    log.time(logIndex) = t;
    log.carPos(:, logIndex) = [x_car; y_car];
    log.carSpeed(logIndex) = car.speed;

    currentLightStates = cell(1, numIntersections);
    for i = 1:numIntersections
        currentLightStates{i} = trafficLights(i).state;
    end
    log.lightStates{logIndex} = currentLightStates;

    logIndex = logIndex + 1;
    t = t + dt;
    % Salvataggio dei dati del veicolo per ogni frame
    agent_data.time = t;
    agent_data.position = [x_car; y_car];       % Posizione della macchina
    agent_data.speed = car.speed;               % Velocità attuale
    agent_data.isStopped = car.stopped;         % Stato se fermo o no
    agent_data.currentIntersectionID = car.nextLight;  % ID dell'incrocio attuale
    
    % Calcolare la distanza dall'incrocio
    angleToNextLight = trafficLights(car.nextLight).position - car.theta;
    if angleToNextLight < 0
        angleToNextLight = angleToNextLight + 2*pi;
    end
    agent_data.distanceToIntersection = angleToNextLight * roadRadius;  % Distanza dall'incrocio
    
    % Stato di tutti i semafori
    trafficLightStates = cell(1, numIntersections);
    for i = 1:numIntersections
        trafficLightStates{i} = trafficLights(i).state;
    end
    agent_data.trafficLightStates = trafficLightStates;  % Stato semafori
    
    % Salvataggio dei dati nel file .mat (versione temporanea per ogni frame)
    save('matfile/agent_data_tmp.mat', 'agent_data');
    movefile('matfile/agent_data_tmp.mat', 'matfile/agent_data.mat');
    
end

%% 6. Salvataggio dati
fields = fieldnames(log);
for i = 1:length(fields)
    if iscell(log.(fields{i}))
        log.(fields{i}) = log.(fields{i})(1:logIndex-1);
    else
        log.(fields{i}) = log.(fields{i})(:,1:logIndex-1);
    end
end
