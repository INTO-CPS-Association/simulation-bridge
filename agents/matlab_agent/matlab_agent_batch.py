import pika
import yaml
import matlab.engine
import logging
import os
from pathlib import Path
from typing import Dict, Union, List, Optional


class RabbitMQClient:
    """
    Simple wrapper for RabbitMQ connection and operations
    """
    def __init__(self, host: str = 'localhost'):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host))
        self.channel = self.connection.channel()

    def declare_queue(self, queue: str):
        """
        Declare the specified queue in RabbitMQ.
        """
        self.channel.queue_declare(queue=queue)
        logging.info(f"Declared queue: {queue}")

    def publish(self, queue: str, message: str):
        """
        Publish a message to a specific queue.
        """
        self.channel.basic_publish(exchange='', routing_key=queue, body=message)
        logging.info(f"Published message to queue: {queue}")

    def subscribe(self, queue: str, callback, auto_ack: bool = True):
        """
        Subscribe to a queue and define the callback to handle messages.
        """
        self.declare_queue(queue)
        self.channel.basic_consume(
            queue=queue,
            on_message_callback=lambda ch, method, props, body: callback(body.decode()),
            auto_ack=auto_ack
        )
        logging.info(f"Subscribed to queue: {queue}")

    def start_consuming(self):
        """
        Start consuming messages from the queue.
        """
        try:
            self.channel.start_consuming()
            logging.info("Started consuming messages.")
        except KeyboardInterrupt:
            self.close()

    def close(self):
        """
        Close the RabbitMQ connection.
        """
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logging.info("RabbitMQ connection closed.")


class MatlabSimulationError(Exception):
    """Custom exception for MATLAB simulation errors."""
    pass


class MatlabSimulator:
    """
    Manages the lifecycle of a MATLAB simulation
    """
    def __init__(self, path: str, file: str):
        self.sim_path = Path(path).resolve()
        self.sim_file = file
        self.eng: Optional[matlab.engine.MatlabEngine] = None
        self._validate()

    def _validate(self):
        """
        Validate the simulation path and file.
        """
        if not (self.sim_path / self.sim_file).exists():
            raise FileNotFoundError(f"Simulation file '{self.sim_file}' not found at {self.sim_path}")
        logging.info(f"Validated simulation file: {self.sim_file} at {self.sim_path}")

    def start(self):
        """
        Start the MATLAB engine and prepare for simulation.
        """
        self.eng = matlab.engine.start_matlab()
        self.eng.eval("clear; clc;", nargout=0)
        self.eng.addpath(str(self.sim_path), nargout=0)
        logging.info(f"Started MATLAB engine for simulation file: {self.sim_file}")

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
        func = os.path.splitext(self.sim_file)[0]
        args = [self._to_matlab(v) for v in inputs.values()]
        logging.info(f"Running simulation function: {func} with inputs: {inputs}")
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
            logging.info("MATLAB engine closed.")


class MatlabAgent:
    REQUEST_QUEUE = 'queue_1'
    RESPONSE_QUEUE = 'queue_2'

    def __init__(self, host: str = 'localhost'):
        logging.basicConfig(level=logging.INFO)
        self.rpc = RabbitMQClient(host)
        # Declare queues
        self.rpc.declare_queue(self.REQUEST_QUEUE)
        self.rpc.declare_queue(self.RESPONSE_QUEUE)
        # Subscribe to incoming messages
        self.rpc.subscribe(self.REQUEST_QUEUE, self.on_request)

    def on_request(self, message: str):
        """
        Handle incoming simulation requests from RabbitMQ.
        """
        data = yaml.safe_load(message)['simulation']
        logging.info(f"Received simulation request: {data['name']}")
        try:
            # Initialize and run MATLAB simulation
            sim = MatlabSimulator(data['path'], data['file'])
            sim.start()
            results = sim.run(data['inputs'], list(data['outputs'].keys()))
            sim.close()

            # Publish results back to RabbitMQ
            reply = yaml.dump({'results': results})
            self.rpc.publish(self.RESPONSE_QUEUE, reply)
            logging.info("Simulation results sent to response queue.")

        except MatlabSimulationError as e:
            logging.error(f"MATLAB simulation error: {e}")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")

    def start(self):
        """
        Start the agent and listen for incoming messages.
        """
        logging.info(f"Listening for requests on {self.REQUEST_QUEUE}...")
        self.rpc.start_consuming()


if __name__ == '__main__':
    agent = MatlabAgent()
    agent.start()
