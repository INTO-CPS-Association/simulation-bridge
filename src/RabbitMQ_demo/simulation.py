import pika
import yaml
import sys

class Simulation:
    def __init__(self, sim_id):
        self.sim_id = sim_id
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.setup_queue()

    def setup_queue(self):
        # Configura binding per ricevere tutti i messaggi destinati a questa simulazione
        self.channel.exchange_declare(
            exchange='ex.bridge.output',
            exchange_type='topic',
            durable=True
        )
        self.queue_name = f'Q.sim.{self.sim_id}'
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        self.channel.queue_bind(
            exchange='ex.bridge.output',
            queue=self.queue_name,
            routing_key=f"*.{self.sim_id}"  # Accetta messaggi da qualsiasi sorgente
        )

    def handle_message(self, ch, method, properties, body):
        try:
            # Carica il corpo del messaggio come YAML
            msg = yaml.safe_load(body)
            print(f" [SIM {self.sim_id}] Ricevuto: {msg}")
            sim_type = msg.get('simulation', {}).get('type', 'batch')
            print(f" [SIM {self.sim_id}] Tipo di simulazione: {sim_type}")
            ch.basic_ack(method.delivery_tag)
        except yaml.YAMLError as e:
            print(f"Errore nel decodificare il messaggio YAML: {e}")
            ch.basic_nack(method.delivery_tag)
            

    def start(self):
        self.channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=self.handle_message
        )
        print(f" [SIM {self.sim_id}] In ascolto...")
        self.channel.start_consuming()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: simulation.py <simulation_id>")
        sys.exit(1)
        
    Simulation(sys.argv[1]).start()
