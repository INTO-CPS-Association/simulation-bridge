import pika
import yaml
import sys
import uuid
import time

class Simulation:
    def __init__(self, sim_id):
        self.sim_id = sim_id
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.setup_infrastructure()
        
    def setup_infrastructure(self):
        # To receive input messages
        self.channel.exchange_declare(
            exchange='ex.bridge.output',
            exchange_type='topic',
            durable=True
        )
        
        # To send simulation result messages
        self.channel.exchange_declare(
            exchange='ex.sim.result',
            exchange_type='topic',
            durable=True
        )
        
        # Queue to receive input commands
        self.input_queue_name = f'Q.sim.{self.sim_id}'
        self.channel.queue_declare(queue=self.input_queue_name, durable=True)
        self.channel.queue_bind(
            exchange='ex.bridge.output',
            queue=self.input_queue_name,
            routing_key=f"*.{self.sim_id}"  # Accept messages from any source
        )
        
    def handle_message(self, ch, method, properties, body):
        try:
            # Load the message body as YAML
            msg = yaml.safe_load(body)
            print(f" [SIM {self.sim_id}] Received: {msg}")
            
            # Extract simulation information
            sim_type = msg.get('simulation', {}).get('type', 'batch')
            source = method.routing_key.split('.')[0]  # Extract the message source
            
            print(f" [SIM {self.sim_id}] Simulation type: {sim_type}")
            print(f" [SIM {self.sim_id}] Source: {source}")

            # Perform the simulation (in a real-world scenario, this would be a complex computation)
            result = self.perform_simulation(sim_type, msg)
            
            # Send the simulation result
            self.send_result(source, result)
            
            # Acknowledge the receipt of the original message
            ch.basic_ack(method.delivery_tag)
            
        except yaml.YAMLError as e:
            print(f"Error decoding YAML message: {e}")
            ch.basic_nack(method.delivery_tag)
        except Exception as e:
            print(f"Error processing the message: {e}")
            ch.basic_nack(method.delivery_tag)
            
    def perform_simulation(self, sim_type, input_data):
        """
        Executes the simulation and returns the result.
        In a real-world case, this would perform the simulation computation.
        """
        print(f" [SIM {self.sim_id}] Executing simulation of type: {sim_type}")
        
        # Simulate processing time
        if sim_type == 'realtime':
            # For real-time simulations, send multiple results sequentially
            return {
                'simulation_id': str(uuid.uuid4()),
                'sim_type': sim_type,
                'timestamp': time.time(),
                'status': 'completed',
                'data': {
                    'result_type': 'realtime',
                    'metrics': {
                        'accuracy': 0.95,
                        'precision': 0.92,
                        'recall': 0.94
                    },
                    'values': [1.2, 3.4, 5.6, 7.8]
                }
            }
        else:  # batch or other types
            # For batch simulations, send a single complete result
            return {
                'simulation_id': str(uuid.uuid4()),
                'sim_type': sim_type,
                'timestamp': time.time(),
                'status': 'completed',
                'data': {
                    'result_type': 'batch',
                    'summary': {
                        'total_iterations': 100,
                        'convergence_rate': 0.001,
                        'execution_time_ms': 345
                    },
                    'output': {
                        'prediction': [10.5, 20.3, 15.7],
                        'confidence': 0.89
                    }
                }
            }
            
    def send_result(self, destination, result):
        """
        Sends the simulation result to the specified destination.
        """
        # Prepare the payload with the destination
        payload = {
            **result,  # Result data
            'source': self.sim_id,  # Simulation identifier
            'destinations': [destination]  # Recipient (e.g., 'dt', 'pt')
        }
        
        # Serialize to YAML
        payload_yaml = yaml.dump(payload, default_flow_style=False)
        
        # Routing key: <source>.result.<destination>
        routing_key = f"{self.sim_id}.result.{destination}"
        
        # Publish the message
        self.channel.basic_publish(
            exchange='ex.sim.result',
            routing_key=routing_key,
            body=payload_yaml,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistent message
                content_type='application/x-yaml',
                message_id=str(uuid.uuid4())
            )
        )
        print(f" [SIM {self.sim_id}] Result sent to {destination}: {payload}")
        
    def start(self):
        self.channel.basic_consume(
            queue=self.input_queue_name,
            on_message_callback=self.handle_message
        )
        print(f" [SIM {self.sim_id}] Listening for simulation requests...")
        self.channel.start_consuming()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: simulation.py <simulation_id>")
        sys.exit(1)
    
    Simulation(sys.argv[1]).start()