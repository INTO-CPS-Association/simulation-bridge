import time
import json
import scipy.io
import matlab.engine
import numpy as np
import pika
import yaml
import threading


class RabbitMQClient:
    def __init__(self, host='localhost'):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host))
        self.channel = self.connection.channel()

    def declare_queue(self, queue_name: str):
        self.channel.queue_declare(queue=queue_name)

    def publish(self, queue: str, message: dict):
        self.channel.basic_publish(exchange='', routing_key=queue, body=json.dumps(message))

    def subscribe(self, queue: str, callback):
        self.declare_queue(queue)
        def on_message(ch, method, properties, body):
            callback(body.decode())
        self.channel.basic_consume(queue=queue, on_message_callback=on_message, auto_ack=True)

    def start_consuming(self):
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.connection.close()


class AgentSimulationRunner:
    def __init__(self, steps=300, agents=2, realtime=True, matfile='agent_data.mat'):
        self.steps = steps
        self.agents = agents
        self.realtime = realtime
        self.matfile = matfile
        self.eng = None
        self.last_step = -1

    def start_engine(self,file_path):
        print("🔧 Avvio MATLAB Engine...")
        self.eng = matlab.engine.start_matlab()
        self.eng.cd(file_path, nargout=0)
        self.eng.eval("clear; clc;", nargout=0)

    def run_simulation(self):
        print("🚀 Avvio simulazione MATLAB...")
        self.eng.eval(f"simulation_agent({self.steps}, {self.agents}, {str(self.realtime).lower()});", nargout=0, background=True)

    def stop_engine(self):
        if self.eng:
            self.eng.quit()
            print("🛑 MATLAB chiuso.")

    def poll_and_stream(self, publisher: RabbitMQClient, queue_name='agent_updates'):
        print("📡 Inizio polling da file e invio dati...")
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
                positions = agent_data.positions.tolist()
                velocities = agent_data.velocities.tolist()

                print(f"[Step {current_step}] Time: {sim_time:.2f}s")
                publisher.publish(queue_name, {
                    "step": current_step,
                    "time": sim_time,
                    "positions": positions,
                    "velocities": velocities
                })

                if not running:
                    print("✅ Simulazione completata.")
                    break

            except FileNotFoundError:
                time.sleep(0.1)
            except Exception as e:
                print(f"❌ Errore durante il polling: {e}")
                break

            time.sleep(0.1)


class SimulationAgent:
    REQUEST_QUEUE = 'queue_1'
    DATA_QUEUE = 'agent_updates'

    def __init__(self, host='localhost'):
        self.rabbit = RabbitMQClient(host)
        self.rabbit.declare_queue(self.REQUEST_QUEUE)
        self.rabbit.declare_queue(self.DATA_QUEUE)

    def start(self):
        print(f"🟢 In ascolto su '{self.REQUEST_QUEUE}' per avviare simulazioni...")
        self.rabbit.subscribe(self.REQUEST_QUEUE, self.on_simulation_request)
        self.rabbit.start_consuming()

    def on_simulation_request(self, message: str):
        print("📥 Ricevuta richiesta simulazione...")
        try:
            config = yaml.safe_load(message)['simulation']
            file_path = config['file_path']
            matfile = config['matfile']
            steps = config['inputs'].get('steps', 300)
            agents = config['inputs'].get('agents', 2)
            realtime = config['inputs'].get('realtime', True)
            

            runner = AgentSimulationRunner(steps=steps, agents=agents, realtime=realtime, matfile=matfile)
            runner.start_engine(file_path)
            runner.run_simulation()

            # Stream in real-time
            runner.poll_and_stream(self.rabbit, queue_name=self.DATA_QUEUE)

            runner.stop_engine()
        except Exception as e:
            print(f"❌ Errore nella simulazione: {e}")


if __name__ == '__main__':
    agent = SimulationAgent()
    agent.start()
