"""
This is a simple example script to demonstrate how to interact externally with the MATLAB agent.
The script sets up communication channels using RabbitMQ, sends simulation requests to the MATLAB agent,
and listens for results. It uses YAML for message formatting and threading to handle asynchronous listening.
"""
import pika
import yaml
import threading
import uuid


class SimpleUsageMatlabAgent:
    def __init__(self, agent_id="dt"):
        self.agent_id = agent_id
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.setup_channels()
        
    def setup_channels(self):
        """
        Setup exchanges and queues for agent communication
        """
        # Exchange for sending commands to agents
        self.channel.exchange_declare(
            exchange='ex.bridge.output',
            exchange_type='topic',
            durable=True
        )
        
        # Exchange for receiving results from agents
        self.channel.exchange_declare(
            exchange='ex.sim.result',
            exchange_type='topic',
            durable=True
        )
        
        # Queue for receiving specific results from MATLAB Agent
        self.result_queue = f'Q.{self.agent_id}.matlab.result'
        self.channel.queue_declare(queue=self.result_queue, durable=True)

        # Bind queue to ex.sim.result with routing key `matlab.result.{agent_id}`
        self.channel.queue_bind(
            exchange='ex.sim.result',
            queue=self.result_queue,
            routing_key=f"matlab.result.{self.agent_id}"
        )

        print(f"[{self.agent_id.upper()}] Infrastructure configured successfully.")
        
    def send_request(self, payload_data):
        """
        Send simulation request to MATLAB agent
        """
        # Build payload
        payload = {
            **payload_data,
            'destinations': ['matlab'],
            'request_id': str(uuid.uuid4())
        }
        
        # Convert to YAML
        payload_yaml = yaml.dump(payload, default_flow_style=False)
        
        # Routing key: {agent_id}.matlab
        routing_key = f"{self.agent_id}.matlab"
        
        # Send message
        self.channel.basic_publish(
            exchange='ex.bridge.output',
            routing_key=routing_key,
            body=payload_yaml,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/x-yaml',
                message_id=str(uuid.uuid4())
            )
        )
        print(f"[{self.agent_id.upper()}] Message sent to matlab: {payload}")

    def handle_result(self, ch, method, properties, body):
        """
        Handle simulation results
        """
        try:
            result = yaml.safe_load(body)
            print(f"\n[{self.agent_id.upper()}] Result received from MATLAB:")
            print(f"Result: {result}")
            print("-" * 40)
            ch.basic_ack(method.delivery_tag)
            
        except Exception as e:
            print(f"Error processing result: {e}")
            ch.basic_nack(method.delivery_tag)
    
    def start_listening(self):
        """
        Start listening for simulation results
        """
        self.channel.basic_consume(
            queue=self.result_queue,
            on_message_callback=self.handle_result
        )
        print(f"[{self.agent_id.upper()}] Listening for results on routing key 'matlab.result.{self.agent_id}'...")
        self.channel.start_consuming()
        
    def load_yaml(self, file_path):
        """
        Load YAML file
        """
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)


def start_listener(agent_id):
    """
    Start listener in separate thread
    """
    agent = SimpleUsageMatlabAgent(agent_id)
    agent.start_listening()


if __name__ == "__main__":
    agent_id = "dt"
    
    # Start listener in separate thread
    listener_thread = threading.Thread(target=start_listener, args=(agent_id,))
    listener_thread.daemon = True
    listener_thread.start()
    
    # Create main instance for sending requests
    agent = SimpleUsageMatlabAgent(agent_id)
    
    try:
        # Example: You can load simulation data from a YAML file here
        simulation_data = agent.load_yaml("../api/simulation.yaml")
                
        # Send simulation request
        agent.send_request(simulation_data)
        
        print("\nPress Ctrl+C to terminate the program...")
        while True:
            pass
            
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    except Exception as e:
        print(f"Error: {e}")