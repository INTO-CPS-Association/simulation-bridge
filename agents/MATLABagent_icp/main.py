import subprocess
import mmap
import struct
import time
import os
import yaml

def load_config(config_path='config.yaml'):
    """Funzione per caricare la configurazione dal file YAML"""
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def run_simulation(config):
    """Funzione principale per eseguire la simulazione"""
    working_dir = os.getcwd()

    # Avvia MATLAB in background e stampa output in tempo reale
    matlab_process = subprocess.Popen(
        f"matlab -batch \"cd('{working_dir}'); sim = {config['simulation']['matlab_function']}(); sim.run();\"",
        shell=True
    )

    # Attendi che MATLAB crei il file shared_memory.bin
    timeout = 10  # secondi
    start_time = time.time()
    while True:
        shared_memory_file = config['simulation'].get('shared_memory_file', 'shared_memory.bin')
        if os.path.exists(shared_memory_file) and os.path.getsize(shared_memory_file) >= 128:
            break
        if time.time() - start_time > timeout:
            raise TimeoutError("Timeout in attesa di shared_memory.bin pronto")
        time.sleep(0.1)

    try:
        with open(shared_memory_file, 'r+b') as f:
            shm = mmap.mmap(f.fileno(), 0)
            
            # Invia segnale di start a MATLAB
            shm.seek(122)  # Posizione di start_signal
            shm.write(struct.pack('B', 1))
            
            # Leggi input_data dal file YAML
            input_data = config['simulation']['input_data']  # Qui carichiamo i dati di input dalla configurazione
            input_data = input_data + [0.0] * (config['simulation']['input_size'] - len(input_data))  # Completa gli input se necessario

            stop_type = config['simulation']['stop_condition']['type']
            stop_value = config['simulation']['stop_condition']['value']
            
            while True:
                # Scrivi input
                shm.seek(0)
                shm.write(struct.pack(f'{config["simulation"]["input_size"]}d', *input_data))

                # Segnala input pronto
                shm.seek(120)
                shm.write(struct.pack('B', 1))
                
                # Attendi output pronto
                while True:
                    shm.seek(121)
                    if struct.unpack('B', shm.read(1))[0] == 1:
                        break
                    time.sleep(0.01)
                
                # Leggi output
                shm.seek(80)
                output = struct.unpack(f'{config["simulation"]["output_size"]}d', shm.read(40))
                print(f"Output: {output}")
                
                # Resetta flag
                shm.seek(121)
                shm.write(struct.pack('B', 0))
                
                # Condizione di stop
                if stop_type == "threshold" and all(pos >= stop_value for pos in output):
                    print("Condizione di stop raggiunta!")
                    break
                elif stop_type == "time" and time.time() - start_time >= stop_value:
                    print("Timeout raggiunto!")
                    break
    finally:
        matlab_process.terminate()
        matlab_process.wait()
        if os.path.exists(shared_memory_file):
            os.remove(shared_memory_file)
        print("Simulazione completata.")

if __name__ == "__main__":
    config = load_config('config.yaml')  # Carica la configurazione
    run_simulation(config)  # Esegui la simulazione con la configurazione letta
