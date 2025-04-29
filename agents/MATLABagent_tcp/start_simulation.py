#!/usr/bin/env python3
"""
start_simulation.py - Script di avvio per la simulazione MATLAB
Questo script permette di avviare rapidamente la simulazione con parametri specifici.
"""
import argparse
import os
import sys
from main import MatlabSimulationClient, SimulationController

def parse_arguments():
    """Parse gli argomenti della riga di comando"""
    parser = argparse.ArgumentParser(description='Avvia una simulazione MATLAB')
    parser.add_argument('--port', type=int, default=12345, help='Porta per la comunicazione (default: 12345)')
    parser.add_argument('--gravity', type=float, default=9.81, help='Valore della gravità (default: 9.81)')
    parser.add_argument('--vel-x', type=float, default=1.0, help='Velocità iniziale X (default: 1.0)')
    parser.add_argument('--vel-y', type=float, default=4.0, help='Velocità iniziale Y (default: 4.0)')
    parser.add_argument('--time-step', type=float, default=0.1, help='Passo temporale (default: 0.1)')
    parser.add_argument('--max-time', type=float, default=10.0, help='Tempo massimo di simulazione (default: 10.0)')
    return parser.parse_args()

def main():
    """Funzione principale"""
    args = parse_arguments()
    
    # Costruisci lo script MATLAB con i parametri forniti
    matlab_script = f"""
    params = struct(...
        'timeStep', {args.time_step}, ...
        'maxTime', {args.max_time}, ...
        'initialPosition', [0, 0], ...
        'initialVelocity', [{args.vel_x}, {args.vel_y}], ...
        'gravity', {args.gravity}, ...
        'mass', 1.0, ...
        'logFrequency', 5, ...
        'port', {args.port}, ...
        'host', 'localhost' ...
    );
    simulation(params)
    """
    
    # Salva lo script in un file temporaneo
    temp_script_path = os.path.join(os.getcwd(), 'temp_simulation_script.m')
    with open(temp_script_path, 'w') as f:
        f.write(matlab_script)
    print(f"Script MATLAB temporaneo salvato in: {temp_script_path}")
    
    # Costruisci gli argomenti per SimulationController
    controller_args = argparse.Namespace(
        host='localhost',
        port=args.port,
        script=f"run('{temp_script_path}')",
        log=None,
        no_gui=True  # Forza la modalità headless
    )
    
    # Esegui il controller
    controller = SimulationController(controller_args)
    try:
        controller.run()
    except KeyboardInterrupt:
        print("\nInterruzione da tastiera. Arresto in corso...")
    finally:
        # Pulisci il file temporaneo
        if os.path.exists(temp_script_path):
            os.remove(temp_script_path)
            print(f"File temporaneo {temp_script_path} rimosso.")

if __name__ == "__main__":
    main()