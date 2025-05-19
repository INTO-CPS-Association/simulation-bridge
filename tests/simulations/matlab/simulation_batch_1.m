function [x_final, y_final, speed_final, time_elapsed] = simulation_1(x0, y0, speed0, acceleration, angle_deg, simulation_time)
    % SIMULAZIONE MOVIMENTO AUTO 2D
    % Input:
    %   x0, y0: posizione iniziale (m)
    %   speed0: velocità iniziale (m/s)
    %   acceleration: accelerazione (m/s^2)
    %   angle_deg: direzione iniziale in gradi (0-360°)
    %   simulation_time: tempo totale simulazione (s)
    %
    % Output:
    %   x_final, y_final: posizione finale (m)
    %   speed_final: velocità finale (m/s)
    %   time_elapsed: tempo effettivo simulato (s)

    % Converti angolo in radianti
    angle_rad = deg2rad(angle_deg);
    
    % Componenti vettoriali della velocità iniziale
    vx0 = speed0 * cos(angle_rad);
    vy0 = speed0 * sin(angle_rad);
    
    % Componenti dell'accelerazione
    ax = acceleration * cos(angle_rad);
    ay = acceleration * sin(angle_rad);
    
    % Calcolo tempo effettivo (evita casi con accelerazione negativa e velocità 0)
    if acceleration >= 0
        time_elapsed = simulation_time;
    else
        % Tempo fino a fermarsi (v = v0 + a*t => t = -v0/a)
        stop_time = -speed0/acceleration;
        time_elapsed = min(simulation_time, stop_time);
    end
    
    % Equazioni del moto uniformemente accelerato
    x_final = x0 + vx0 * time_elapsed + 0.5 * ax * time_elapsed^2;
    y_final = y0 + vy0 * time_elapsed + 0.5 * ay * time_elapsed^2;
    
    % Velocità finale
    speed_final = speed0 + acceleration * time_elapsed;
    if speed_final < 0
        speed_final = 0;  % L'auto non può andare indietro in questo modello
    end
    
    % Debug info (opzionale)
    fprintf('Simulazione completata:\n');
    fprintf('Tempo simulato: %.2f s\n', time_elapsed);
    fprintf('Posizione finale: (%.2f, %.2f) m\n', x_final, y_final);
    fprintf('Velocità finale: %.2f m/s\n\n', speed_final);
end
