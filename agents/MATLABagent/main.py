import os
import yaml
import logging
from .rabbitmq.rabbitmq_client import RabbitMQClient
from .batch import handle_batch_simulation
from .streaming import handle_streaming_simulation


class UnifiedAgent:
    def __init__(self, config_filename='config_agent.yaml'):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)s: %(message)s'
        )
        # Abbassa il livello di log di tutti i logger usati da pika
        for logger_name in logging.root.manager.loggerDict:
            if logger_name.startswith("pika"):
                logging.getLogger(logger_name).setLevel(logging.CRITICAL)

        # Percorso dinamico
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, config_filename)

        # Carica configurazione
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.REQUEST_QUEUE = self.config['queues']['request']
        self.RESPONSE_QUEUE = self.config['queues']['response']
        self.DATA_QUEUE = self.config['queues']['data']

        self.rpc = RabbitMQClient(self.config['rabbitmq'])

        for queue in (self.REQUEST_QUEUE, self.RESPONSE_QUEUE, self.DATA_QUEUE):
            self.rpc.declare_queue(queue)

        self.rpc.subscribe(self.REQUEST_QUEUE, self.on_request)

    def on_request(self, message: str):
        try:
            parsed = yaml.safe_load(message)
            sim_type = parsed.get('simulation', {}).get('type', 'batch')
            logging.info(f"Received simulation_type: {sim_type}")

            if sim_type == 'batch':
                handle_batch_simulation(parsed, self.rpc, self.RESPONSE_QUEUE)
            elif sim_type == 'streaming':
                handle_streaming_simulation(parsed, self.rpc, self.DATA_QUEUE)
            else:
                logging.error(f"Unknown simulation type: {sim_type}")
        except Exception as e:
            logging.error(f"Error processing request: {e}")

    def start(self):
        logging.info(f"MATLAB Agent ready to receive requests on queue '{self.REQUEST_QUEUE}'")
        self.rpc.start_consuming()

def main():
    agent = UnifiedAgent()
    agent.start()

if __name__ == '__main__':
    main()
