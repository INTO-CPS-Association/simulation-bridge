import time
import scipy.io
import matlab.engine
import yaml
import logging
from rabbitmq.rabbitmq_client import RabbitMQClient
import numpy
import os

class AgentSimulationRunner:
    def __init__(self, filename: str = 'simulation', matfile: str = 'agent_data.mat', **kwargs):
        """
        Initializes the simulation runner with flexible parameters.
        
        Args:
            filename: The MATLAB simulation function name to run
            matfile: Path to the MAT file for data exchange
            **kwargs: Additional parameters that will be passed to the simulation
                     (can include steps, agents, realtime, outputs, etc.)
        """
        self.filename = filename
        self.matfile = matfile
        self.params = kwargs  # Store all additional parameters
        self.eng = None
        self.last_step = -1
        self.expected_outputs = kwargs.get('outputs', {})  # Store expected output structure
        
    def start_engine(self, file_path: str):
        logging.info("Starting MATLAB Engine...")
        self.eng = matlab.engine.start_matlab()
        self.eng.cd(file_path, nargout=0)
        self.eng.eval("clear; clc;", nargout=0)
        
    def run_simulation(self):
        """
        Runs the MATLAB simulation with dynamic parameters from the 'inputs' section.
        Preserves the input order as defined in the config file.
        """
        logging.info(f"Launching MATLAB interactive simulation: {self.filename}")
        #print(f"[DEBUG] Parsed param types: {[type(self.params[k]) for k in self.params if k != 'outputs']}")

        # Extract all inputs
        inputs = self.params  

        param_list = []

        for key, value in inputs.items():
            if key == 'outputs':
                continue
            # Cast boolean strings
            if isinstance(value, str) and value.lower() in ['true', 'false']:
                formatted_value = value.lower()
            elif isinstance(value, bool):
                formatted_value = str(value).lower()
            elif isinstance(value, str):
                try:
                    float(value)  # Check if it's numeric
                    formatted_value = value  # numeric string, no quotes
                except ValueError:
                    formatted_value = f"'{value}'"  # true string
            else:
                formatted_value = str(value)

            param_list.append(formatted_value)

        param_string = ", ".join(param_list)
        cmd = f"{self.filename}({param_string});"

        logging.info(f"Executing MATLAB command: {cmd}")
        self.eng.eval(cmd, nargout=0, background=True)
        
            
    def stop_engine(self):
        if self.eng:
            self.eng.quit()
            logging.info("MATLAB Engine closed.")
            
    def matlab_to_python(self, obj):
        """Recursively convert MAT objects to Python types."""
        if isinstance(obj, numpy.ndarray):
            if obj.dtype.names:  # Struct array
                if obj.size == 1:  # Single struct
                    return {name: self.matlab_to_python(obj[name][0]) for name in obj.dtype.names}
                else:  # Array of structs
                    return [self.matlab_to_python(obj[i]) for i in range(obj.size)]
            elif obj.dtype == 'object':  # Cell array
                return [self.matlab_to_python(item) for item in obj]
            else:  # Regular array
                return obj.tolist()
        elif isinstance(obj, numpy.generic):
            return obj.item()
        elif isinstance(obj, dict):
            return {key: self.matlab_to_python(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self.matlab_to_python(item) for item in obj]
        elif isinstance(obj, (int, float, str, bool)) or obj is None:
            return obj
        else:
            try:
                return {name: self.matlab_to_python(getattr(obj, name)) for name in dir(obj) if not name.startswith('__')}
            except AttributeError:
                return str(obj)
                
    def poll_and_stream(self, publisher: RabbitMQClient, queue_name: str = 'agent_updates', expected_outputs=None):
        """
        Poll MAT file for changes and stream updates according to expected output structure.
        
        Args:
            publisher: RabbitMQ client for publishing updates
            queue_name: Queue name for publishing updates
            expected_outputs: Structure defining expected data types for outputs (optional)
        """
        logging.info("Polling simulation data and streaming updates...")
        
        # Use provided expected_outputs or fallback to class attribute
        output_structure = expected_outputs if expected_outputs is not None else self.expected_outputs
        
        last_mtime = None
        while True:
            try:
                current_mtime = os.path.getmtime(self.matfile)
                if last_mtime is None or current_mtime > last_mtime:
                    logging.info(f"Detected new data in {self.matfile}.")
                    last_mtime = current_mtime
                    
                    data = scipy.io.loadmat(self.matfile, struct_as_record=False, squeeze_me=True)
                    converted_data = {}
                    
                    for key in data:
                        if not key.startswith('__'):  # Exclude MATLAB metadata
                            converted_data[key] = self.matlab_to_python(data[key])
                    
                    # Filter data based on expected outputs if provided
                    if output_structure:
                        filtered_data = self._filter_data_by_structure(converted_data, output_structure)
                        publisher.publish(queue_name, yaml.dump(filtered_data))
                        logging.info(f"Published filtered data according to expected outputs.")
                    else:
                        publisher.publish(queue_name, yaml.dump(converted_data))
                        logging.info(f"Published all data from {self.matfile}.")
                        
                    logging.info(f"Data published at {time.ctime(current_mtime)}.")
                    
            except FileNotFoundError:
                logging.warning(f"File {self.matfile} not found, retrying...")
            except Exception as e:
                logging.error(f"Error polling or processing data: {e}")
                break
                
            time.sleep(0.1)  # Polling interval
            
    def _filter_data_by_structure(self, data, structure):
        """
        Filter and format data according to expected output structure.
        
        Args:
            data: Raw data from MAT file
            structure: Expected output structure with types
            
        Returns:
            Filtered data matching the expected structure
        """
        result = {}
        
        # For each expected output category
        for category, expected in structure.items():
            if category in data:
                if isinstance(expected, dict):
                    # If this is a nested structure
                    result[category] = self._filter_data_by_structure(data[category], expected)
                else:
                    # Include this field as is
                    result[category] = data[category]
            else:
                logging.warning(f"Expected output '{category}' not found in simulation data")
                
        return result
    
def handle_interactive_simulation(parsed_data: dict, rpc_client: RabbitMQClient, data_queue: str):
    """
    Process an interactive simulation request and stream updates.
    Automatically passes all configuration parameters including outputs to the simulation runner.
    """
    config = parsed_data['simulation']
    logging.info("Handling interactive simulation request...")
    # print("Config: ", config)
    
    # Estrai il percorso della simulazione (gestisce sia 'file_path' che 'path')
    file_path = config.get('file_path', config.get('path'))
    if not file_path:
        raise ValueError("File path not found in configuration (needs 'file_path' or 'path')")
    
    # Estrai il nome del file di simulazione (gestisce sia 'filename', 'file_name' o 'file')
    filename = config.get('filename', config.get('file_name', config.get('file', '')))
    if filename:
        # Rimuovi l'estensione .m se presente
        filename = filename.replace('.m', '')
    else:
        raise ValueError("Simulation filename not found (needs 'filename', 'file_name' or 'file')")
    
    # Crea il runner e passa tutti i parametri dal file di configurazione
    # Inizializza con i parametri essenziali
    runner_params = {
        'filename': filename,
        'matfile': config.get('matfile', 'agent_data.mat')
    }
    
    # Aggiungi tutti gli input dalla configurazione
    if 'inputs' in config and isinstance(config['inputs'], dict):
        runner_params.update(config['inputs'])
    
    # Aggiungi gli output desiderati
    if 'outputs' in config and isinstance(config['outputs'], dict):
        runner_params['outputs'] = config['outputs']
    
    # Crea il runner con tutti i parametri
    runner = AgentSimulationRunner(**runner_params)
    
    try:
        runner.start_engine(file_path)
        runner.run_simulation()
        runner.poll_and_stream(rpc_client, queue_name=data_queue, expected_outputs=config.get('outputs'))
    finally:
        runner.stop_engine()