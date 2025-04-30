import pika
import yaml
import threading
import time
import json
import logging

class RabbitMQClient:
    def __init__(self, host='localhost'):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host))
        self.channel = self.connection.channel()
        print(f"✅ Connesso a RabbitMQ su {host}")

    def declare_queue(self, queue: str):
        self.channel.queue_declare(queue=queue)

    def publish(self, queue: str, message: str):
        self.channel.basic_publish(exchange='', routing_key=queue, body=message)
        print(f"📤 Inviata richiesta su '{queue}'")

    def subscribe(self, queue: str, callback):
        self.declare_queue(queue)
        def on_message(ch, method, props, body):
            callback(body.decode())
        self.channel.basic_consume(queue=queue, on_message_callback=on_message, auto_ack=True)

    def start_consuming(self):
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.close()

    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            print("🔌 Connessione RabbitMQ chiusa.")


class SimulationClient:
    REQUEST_QUEUE = 'queue_1'
    LIVE_DATA_QUEUE = 'agent_updates'

    def __init__(self, host='localhost'):
        self.sender = RabbitMQClient(host)
        self.listener = RabbitMQClient(host)

    def send_simulation_request(self, sim_name='SimulazioneInterattiva'):
        sim_request = {
            'simulation': {
                'name': sim_name,
                'file_path': '/Users/marcomelloni/Desktop/AU_University/simulation-bridge/tests/simulations/matlab/',
                'matfile': '/Users/marcomelloni/Desktop/AU_University/simulation-bridge/tests/simulations/matlab/matfile/agent_data.mat',
                'file': 'simulation_agent.m',
                'inputs': {
                    'steps': 300,
                    'agents': 2,
                    'realtime': False
                },
                'outputs': {
                    'result': None
                }
            }
        }
        yaml_msg = yaml.dump(sim_request)
        self.sender.publish(self.REQUEST_QUEUE, yaml_msg)

    def listen_live_data(self):
        def on_data(message: str):
            try:
                data = json.loads(message)
                print(f"\n📡 Step {data['step']} | Time: {data['time']:.2f}s")
                for i, (pos, vel) in enumerate(zip(data['positions'], data['velocities'])):
                    print(f" - Agente {i+1}: Pos={pos}, Vel={vel}")
            except Exception as e:
                print(f"Errore nella ricezione dati: {e}")

        self.listener.subscribe(self.LIVE_DATA_QUEUE, on_data)

        threading.Thread(target=self.listener.start_consuming, daemon=True).start()
        print(f"🟢 In ascolto su '{self.LIVE_DATA_QUEUE}'...")

    def run(self):
        self.listen_live_data()
        time.sleep(0.5)  # piccolo delay per assicurare che il consumer sia pronto
        self.send_simulation_request()

        print("⏳ Attendi che la simulazione invii i dati in tempo reale...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.sender.close()
            self.listener.close()


if __name__ == '__main__':
    client = SimulationClient()
    client.run()
