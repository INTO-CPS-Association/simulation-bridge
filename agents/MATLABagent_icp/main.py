import subprocess
import mmap
import struct
import time
import os
import yaml

def load_config(config_path='config.yaml'):
    """Function to load the configuration from the YAML file"""
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def run_simulation(config):
    """Main function to run the simulation"""
    working_dir = os.getcwd()

    # Start MATLAB in the background and print output in real-time
    matlab_process = subprocess.Popen(
        f"matlab -batch \"cd('{working_dir}'); sim = {config['simulation']['matlab_function']}(); sim.run();\"",
        shell=True
    )

    # Wait for MATLAB to create the shared_memory.bin file
    timeout = 10  # seconds
    start_time = time.time()
    while True:
        shared_memory_file = config['simulation'].get('shared_memory_file', 'shared_memory.bin')
        if os.path.exists(shared_memory_file) and os.path.getsize(shared_memory_file) >= 128:
            break
        if time.time() - start_time > timeout:
            raise TimeoutError("Timeout waiting for shared_memory.bin to be ready")
        time.sleep(0.1)

    try:
        with open(shared_memory_file, 'r+b') as f:
            shm = mmap.mmap(f.fileno(), 0)
            
            # Send start signal to MATLAB
            shm.seek(122)  # Position of start_signal
            shm.write(struct.pack('B', 1))
            
            # Read input_data from the YAML file
            input_data = config['simulation']['input_data']  # Load input data from the configuration
            input_data = input_data + [0.0] * (config['simulation']['input_size'] - len(input_data))  # Pad inputs if necessary

            stop_type = config['simulation']['stop_condition']['type']
            stop_value = config['simulation']['stop_condition']['value']
            
            while True:
                # Write input
                shm.seek(0)
                shm.write(struct.pack(f'{config["simulation"]["input_size"]}d', *input_data))

                # Signal input ready
                shm.seek(120)
                shm.write(struct.pack('B', 1))
                
                # Wait for output ready
                while True:
                    shm.seek(121)
                    if struct.unpack('B', shm.read(1))[0] == 1:
                        break
                    time.sleep(0.01)
                
                # Read output
                shm.seek(80)
                output = struct.unpack(f'{config["simulation"]["output_size"]}d', shm.read(40))
                print(f"Output: {output}")
                
                # Reset flag
                shm.seek(121)
                shm.write(struct.pack('B', 0))
                
                # Stop condition
                if stop_type == "threshold" and all(pos >= stop_value for pos in output):
                    print("Stop condition reached!")
                    break
                elif stop_type == "time" and time.time() - start_time >= stop_value:
                    print("Timeout reached!")
                    break
    finally:
        matlab_process.terminate()
        matlab_process.wait()
        if os.path.exists(shared_memory_file):
            os.remove(shared_memory_file)
        print("Simulation completed.")

if __name__ == "__main__":
    config = load_config('config.yaml')  # Load the configuration
    run_simulation(config)  # Run the simulation with the loaded configuration
