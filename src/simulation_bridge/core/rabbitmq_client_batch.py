# rabbitmq_client_batch.py
import yaml
from protocols.rabbitmq.rabbitmq_client import RabbitMQClient


def load_simulation_data(filename: str) -> dict:
    with open(filename, 'r') as file:
        return yaml.safe_load(file)


def on_response(ch, method, properties, body):
    print(f"[✓] Received simulation results: {body.decode()}")
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    # Load configuration and simulation data
    simulation_data = load_simulation_data('simulation.yml')
    
    # Initialize RabbitMQ client
    rmq_client = RabbitMQClient()
    
    # Declare queues
    rmq_client.declare_queue('queue_simulation')
    rmq_client.declare_queue('queue_response')
    
    # Publish simulation message
    message = yaml.dump({'simulation': simulation_data['simulation']})

    rmq_client.publish('queue_simulation', message)
    print(f"[→] Sent simulation data: {message}")
    
    # Set up consumer for the response
    rmq_client.consume('queue_response', on_response)
    print("[⏳] Waiting for results on 'queue_response'")
    
    try:
        rmq_client.start_consuming()
    except KeyboardInterrupt:
        print("\n[!] Interrupt received. Closing connection...")
        rmq_client.close()


if __name__ == '__main__':
    main()
