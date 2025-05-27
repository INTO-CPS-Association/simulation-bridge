import pika
import yaml
import os
import threading
import uuid
import sys

class DigitalTwin:
    def __init__(self, dt_id="dt"):
        self.dt_id = dt_id
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.setup_infrastructure()
        
    def setup_infrastructure(self):
        # Exchange to send commands to simulators
        self.channel.exchange_declare(
            exchange='ex.input.bridge',
            exchange_type='topic',
            durable=True
        )
        
        # Exchange to receive results from simulators
        self.channel.exchange_declare(
            exchange='ex.bridge.result',
            exchange_type='topic',
            durable=True
        )
        
        # Queue to receive results
        self.result_queue_name = f'Q.{self.dt_id}.result'
        self.channel.queue_declare(queue=self.result_queue_name, durable=True)
        self.channel.queue_bind(
            exchange='ex.bridge.result',
            queue=self.result_queue_name,
            routing_key=f"*.result"  # Receive all results
        )
        
    def send_simulation_request(self, payload_data):
        """
        Sends a simulation request to the specified simulators.
        """
        payload = {
            **payload_data,  # Add payload data
            'request_id': str(uuid.uuid4()),  # Unique identifier for the request
        }
        
        # Serialize the payload in YAML format
        payload_yaml = yaml.dump(payload, default_flow_style=False)
        
        # Publish the message to RabbitMQ
        self.channel.basic_publish(
            exchange='ex.input.bridge',
            routing_key=self.dt_id,  # e.g., 'dt', 'pt', 'mockpt'
            body=payload_yaml,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/x-yaml',
                message_id=str(uuid.uuid4())
            )
        )
        
    def handle_result(self, ch, method, properties, body):
        """
        Handles simulation results.
        """
        try:
            # Extract information from the routing key
            source = method.routing_key.split('.')[0]  # Simulator that sent the result
            
            # Load the message body as YAML
            result = yaml.safe_load(body)
            
            print(f"\n[{self.dt_id.upper()}] Received result from {source}:")
            print(f"Result: {result}")
            print("-" * 50)
            
            # Acknowledge the message
            ch.basic_ack(method.delivery_tag)
            
        except yaml.YAMLError as e:
            print(f"Error decoding YAML result: {e}")
            ch.basic_nack(method.delivery_tag)
        except Exception as e:
            print(f"Error processing the result: {e}")
            ch.basic_nack(method.delivery_tag)
    
    def start_listening(self):
        """
        Starts listening for simulation results.
        """
        self.channel.basic_consume(
            queue=self.result_queue_name,
            on_message_callback=self.handle_result
        )
        print(f" [{self.dt_id.upper()}] Listening for simulation results...")
        self.channel.start_consuming()
        
    def load_yaml_file(self, file_path):
        """
        Loads the content of a YAML file.
        """
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)


def start_dt_listener(dt_id):
    """
    Function to start listening for results in a separate thread.
    """
    dt = DigitalTwin(dt_id)
    dt.start_listening()


if __name__ == "__main__":
    dt_id = "dt"
    if len(sys.argv) > 1:
        dt_id = sys.argv[1]
    
    # Start the listener thread for results
    listener_thread = threading.Thread(target=start_dt_listener, args=(dt_id,))
    listener_thread.daemon = True  # The thread will terminate when the main program ends
    listener_thread.start()
    
    # Create a main instance to send requests
    dt = DigitalTwin(dt_id)
    
    # Load the simulation.yaml file from the same folder
    base_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_file_path = os.path.join(base_dir, 'simulation.yaml')
    
    try:
        # Load the payload from the YAML file
        simulation_payload = dt.load_yaml_file(yaml_file_path)
        
        # Send the simulation request
        dt.send_simulation_request(
            payload_data=simulation_payload
        )
        
        print("\nPress Ctrl+C to terminate the program...")
        # Keep the program running to receive results
        while True:
            pass
            
    except KeyboardInterrupt:
        print("\nProgram terminated by the user.")
    except Exception as e:
        print(f"Error: {e}")