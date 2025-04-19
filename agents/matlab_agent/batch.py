import yaml
import logging
from rabbitmq.rabbitmq_client import RabbitMQClient
import matlab.engine
import os
from pathlib import Path
from typing import Dict, Union, List, Optional
from datetime import datetime


class MatlabSimulator:
    """
    Manages the lifecycle of a MATLAB simulation
    """
    def __init__(self, path: str, file: str, function_name: Optional[str] = None):
        self.sim_path = Path(path).resolve()
        self.sim_file = file
        self.function_name = function_name or os.path.splitext(file)[0]  # Default to file name if no function name provided
        self.eng: Optional[matlab.engine.MatlabEngine] = None
        self._validate()

    def _validate(self):
        """
        Validate the simulation path and file.
        """
        if not (self.sim_path / self.sim_file).exists():
            raise FileNotFoundError(f"Simulation file '{self.sim_file}' not found at {self.sim_path}")

    def start(self):
        """
        Start the MATLAB engine and prepare for simulation.
        """
        self.eng = matlab.engine.start_matlab()
        self.eng.eval("clear; clc;", nargout=0)
        self.eng.addpath(str(self.sim_path), nargout=0)

    def run(self,
            inputs: Dict[str, Union[float, int, list, matlab.double]],
            outputs: List[str]
    ) -> Dict[str, Union[float, list]]:
        """
        Run the MATLAB simulation and return the results.
        """
        if not self.eng:
            raise MatlabSimulationError("MATLAB engine is not started.")
        self.eng.eval("clear variables;", nargout=0)
        
        func = self.function_name  # Use the user-specified function name
        args = [self._to_matlab(v) for v in inputs.values()]
        result = self.eng.feval(func, *args, nargout=len(outputs))
        return {name: self._from_matlab(result[i]) for i, name in enumerate(outputs)}

    def _to_matlab(self, v):
        """
        Convert Python values to MATLAB types.
        """
        if isinstance(v, (list, tuple)):
            return matlab.double(list(v))
        if isinstance(v, (int, float)):
            return matlab.double(float(v))
        return v

    def _from_matlab(self, v):
        """
        Convert MATLAB types back to Python types.
        """
        if isinstance(v, matlab.double):
            try:
                return v[0][0]
            except Exception:
                return [list(row) for row in v]
        return v

    def close(self):
        """
        Close the MATLAB engine.
        """
        if self.eng:
            self.eng.quit()


class MatlabSimulationError(Exception):
    """Custom exception for MATLAB simulation errors."""
    pass


def handle_batch_simulation(parsed_data: dict, rpc_client: RabbitMQClient, response_queue: str):
    data = parsed_data['simulation']
    logging.info(f"Processing batch simulation: {data.get('name', 'Unnamed')}")

    sim_path = data.get('path')
    sim_file = data.get('file')

    if not sim_path or not sim_file:
        error_reply = yaml.dump({
            'status': 'error',
            'simulation': {
                'name': data.get('name', 'unknown'),
                'type': 'batch'
            },
            'error': {
                'message': "Missing 'path' or 'file' in simulation config.",
                'code': 400
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        rpc_client.publish(response_queue, error_reply)
        return

    try:
        sim = MatlabSimulator(sim_path, sim_file)
        sim.start()
        results = sim.run(data['inputs'], list(data['outputs'].keys()))
        sim.close()
    except Exception as e:
        logging.error(f"Simulation failed: {str(e)}", exc_info=True)
        error_reply = yaml.dump({
            'status': 'error',
            'simulation': {
                'name': data.get('name', 'unknown'),
                'type': 'batch'
            },
            'error': {
                'message': str(e),
                'code': 500
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        rpc_client.publish(response_queue, error_reply)
        return

    logging.info("SIMULATION COMPLETED")

    reply = yaml.dump({
        'status': 'success',
        'simulation': {
            'name': data['name'],
            'type': 'batch',
            'outputs': results
        },
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })
    rpc_client.publish(response_queue, reply)
    logging.info("Result published to RabbitMQ on queue '%s'", response_queue)
