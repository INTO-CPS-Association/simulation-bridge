global sim_running;
sim_running = true;

global agent_data;
agent_data = [];

% Esegui simulation_agent in modo asincrono
f = parfeval(@simulation_agent, 0, 300, 2, false);  % nessun output, 300 step, show_agent=2, no grafica

disp("Simulazione avviata in background con parfeval.");
