import matlab.engine
import os
import time

class ModularSimulationManager:
    def __init__(self, sim_folder, setup_func, step_func, term_func):
        self.eng = matlab.engine.start_matlab()
        self.eng.addpath(sim_folder)
        self.setup_func = setup_func
        self.step_func = step_func
        self.term_func = term_func
        
    def _convert_params(self, py_params):
        # Converte i parametri Python in una struct MATLAB
        matlab_params = {}
        for k, v in py_params.items():
            if isinstance(v, list):
                # Converti liste in array MATLAB
                if isinstance(v[0], list):  # Se la lista contiene altre liste (2D)
                    matlab_params[k] = self.eng.cell(v)  # Utilizzare cella in questo caso
                else:
                    matlab_params[k] = self.eng.double(v)  # Altrimenti, usa un array doppio
            elif isinstance(v, (int, float)):
                # Converti numeri in double MATLAB
                matlab_params[k] = float(v)
            else:
                # Lascia altri tipi invariati
                matlab_params[k] = v
        
        # Creazione della struttura MATLAB corretta
        matlab_struct = self.eng.struct()
        for k, v in matlab_params.items():
            matlab_struct = self.eng.setfield(matlab_struct, k, v)
        
        return matlab_struct

    def start(self, params):
        # Converte i parametri Python in una struct MATLAB
        matlab_params = self._convert_params(params)
        
        # Crea l'oggetto SimulationRunner in MATLAB
        self.runner = self.eng.SimulationRunner(matlab_params, self.setup_func, self.step_func, self.term_func, nargout=1)
    
    def get_step(self):
        # Esegue un singolo passo
        return self.eng.step(self.runner, nargout=2)
    
    def run(self, callback, max_steps=100):
        # Esegue la simulazione completa
        for _ in range(max_steps):
            data, terminated = self.get_step()
            # Converti i dati MATLAB in Python
            py_data = {
                'positions': list(data['positions']),
                'velocities': list(data['velocities']),
                'elapsedTime': float(data['elapsedTime'])
            }
            callback(py_data)
            if terminated:
                break
            time.sleep(0.1)  # Pausa tra i passi
    
    def stop(self):
        self.eng.quit()

def print_callback(data):
    print(f"Time: {data['elapsedTime']:.2f}s")
    print(f"Positions: {data['positions']}")
    print("-" * 40)

if __name__ == "__main__":
    # Configurazione
    params = {
        'numAgents': 3,  # Numero intero
        'speedLimit': 1.0,  # Double
        'timeStep': 0.1,  # Double
        'maxTime': 5.0  # Double
    }

    # Percorso della cartella MATLAB
    current_dir = '/Users/marcomelloni/Desktop/AU_University/simulation-bridge/tests/simulations/matlab'

    try:
        manager = ModularSimulationManager(
            sim_folder=current_dir,
            setup_func='setupParticleSimulation',
            step_func='stepParticleSimulation',
            term_func='checkParticleTermination'
        )

        manager.start(params)
        manager.run(print_callback)
    finally:
        manager.stop()
