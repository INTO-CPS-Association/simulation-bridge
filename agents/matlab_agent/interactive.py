import time
import scipy.io
import matlab.engine
import yaml
import logging
from rabbitmq.rabbitmq_client import RabbitMQClient


class AgentSimulationRunner:
    def __init__(self, steps: int = 300, agents: int = 2, realtime: bool = True, matfile: str = 'agent_data.mat'):
        self.steps = steps
        self.agents = agents
        self.realtime = realtime
        self.matfile = matfile
        self.eng = None
        self.last_step = -1

    def start_engine(self, file_path: str):
        logging.info("Starting MATLAB Engine...")
        self.eng = matlab.engine.start_matlab()
        self.eng.cd(file_path, nargout=0)
        self.eng.eval("clear; clc;", nargout=0)

    def run_simulation(self):
        logging.info("Launching MATLAB interactive simulation...")
        cmd = f"simulation_agent({self.steps}, {self.agents}, {str(self.realtime).lower()});"
        self.eng.eval(cmd, nargout=0, background=True)

    def stop_engine(self):
        if self.eng:
            self.eng.quit()
            logging.info("MATLAB Engine closed.")

    def poll_and_stream(self, publisher: RabbitMQClient, queue_name: str = 'agent_updates'):
        logging.info("Polling simulation data and streaming updates...")
        while True:
            try:
                data = scipy.io.loadmat(self.matfile, struct_as_record=False, squeeze_me=True)
                agent_data = data['agent_data']

                current_step = int(agent_data.current_step)
                if current_step == self.last_step:
                    time.sleep(0.1)
                    continue
                self.last_step = current_step

                sim_time = float(agent_data.time)
                running = bool(agent_data.running)
                payload = {
                    "step": current_step,
                    "time": sim_time,
                    "positions": agent_data.positions.tolist(),
                    "velocities": agent_data.velocities.tolist()
                }
                publisher.publish(queue_name, yaml.dump(payload))
                logging.info(f"Step {current_step}: data sent.")

                if not running:
                    logging.info("Interactive simulation completed.")
                    break

            except FileNotFoundError:
                time.sleep(0.1)
            except Exception as e:
                logging.error(f"Polling error: {e}")
                break
            time.sleep(0.1)


def handle_interactive_simulation(parsed_data: dict, rpc_client: RabbitMQClient, data_queue: str):
    """
    Process an interactive simulation request and stream updates.
    """
    config = parsed_data['simulation']
    logging.info("Handling interactive simulation request...")

    file_path = config['file_path']
    runner = AgentSimulationRunner(
        steps=config['inputs'].get('steps', 300),
        agents=config['inputs'].get('agents', 2),
        realtime=config['inputs'].get('realtime', True),
        matfile=config.get('matfile', 'agent_data.mat')
    )

    try:
        runner.start_engine(file_path)
        runner.run_simulation()
        runner.poll_and_stream(rpc_client, queue_name=data_queue)
    finally:
        runner.stop_engine()