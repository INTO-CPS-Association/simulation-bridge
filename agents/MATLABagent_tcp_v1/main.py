import yaml
import socket
import subprocess
import json
import time
import sys

# Function to load configuration from a YAML file
def load_config(config_path):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

# Function to start the MATLAB simulation using the configuration and port
def start_matlab_simulation(config, port):
    matlab_script_path = config['path']  # Path to the MATLAB script
    matlab_script = config['file']      # MATLAB script file name

    # Command to run MATLAB in batch mode and execute the script
    command = [
        'matlab',
        '-batch',
        f"addpath('{matlab_script_path}');"
        f"port = {port};"
        f"cd('{matlab_script_path}');"
        f"run('{matlab_script}');"
    ]
    return subprocess.Popen(
        command, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        text=True
    )

# Function to handle communication with the MATLAB client
def handle_client(conn, inputs):
    # Send input data to MATLAB as a JSON string
    conn.sendall(json.dumps(inputs).encode() + b'\n')
    
    buffer = b""  # Buffer to store incoming data
    while True:
        try:
            chunk = conn.recv(1024)  # Receive data in chunks
            if not chunk:
                print("MATLAB disconnected.")  # MATLAB client disconnected
                break
            buffer += chunk
            while b'\n' in buffer:  # Process complete lines
                line, buffer = buffer.split(b'\n', 1)
                if line.strip():  # Ignore empty lines
                    output = json.loads(line.decode())  # Parse JSON output
                    print("Received output:", output)  # Print received output
        except (json.JSONDecodeError, ConnectionResetError) as e:
            print(f"Error: {e}")  # Handle decoding or connection errors
            break

# Main function to set up the server and manage the MATLAB simulation
def main():
    try:
        # Load configuration from the YAML file
        config = load_config('config.yaml')

        sim_config = config['simulation']  # Extract simulation configuration
        
        HOST = 'localhost'  # Host address
        PORT = 12345        # Fixed port for simplicity
        
        # Create a TCP socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow address reuse
            s.bind((HOST, PORT))  # Bind the socket to the host and port
            s.listen()  # Start listening for incoming connections
            
            print(f"Starting MATLAB simulation on port {PORT}")
            # Start the MATLAB simulation as a subprocess
            matlab_process = start_matlab_simulation(sim_config, PORT)
            
            print("Waiting for MATLAB connection...")
            # Accept a connection from the MATLAB client
            conn, addr = s.accept()
            print(f"Connected to MATLAB client at {addr}")
            
            try:
                # Handle communication with the MATLAB client
                handle_client(conn, sim_config['inputs'])
            finally:
                conn.close()  # Close the connection

    except Exception as e:
        print(f"Error in main: {e}")  # Print any errors that occur
        sys.exit(1)  # Exit the program with an error code

# Entry point of the script
if __name__ == '__main__':
    main()