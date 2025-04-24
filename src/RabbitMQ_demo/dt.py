import pika
import yaml
import os

def send_message(source, destinations, payload_data):
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    # Aggiungi la lista 'destinations' al payload
    payload = {
        **payload_data,  # Aggiungi i dati del payload
        'destinations': destinations  # Aggiungi la lista di destinazioni
    }

    # Serializzazione del payload in formato YAML
    payload_yaml = yaml.dump(payload, default_flow_style=False)

    # Pubblica il messaggio su RabbitMQ
    channel.basic_publish(
        exchange='ex.input.bridge',
        routing_key=source,  # es. 'dt', 'pt', 'mockpt'
        body=payload_yaml,
        properties=pika.BasicProperties(
            delivery_mode=2,
            content_type='application/x-yaml'  # Modificato per rappresentare YAML
        )
    )
    
    print(f" [{source.upper()}] Inviato: {payload_yaml}")
    connection.close()


def load_yaml_file(file_path):
    """Carica il contenuto di un file YAML"""
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

if __name__ == "__main__":
    # Carica il file simulation.yaml dalla stessa cartella
    base_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_file_path = os.path.join(base_dir, 'simulation.yaml')

    # Carica il payload dal file YAML
    simulation_payload = load_yaml_file(yaml_file_path)

    # Esempio: invio il messaggio da DT alla simulazione
    send_message(
        source='dt',
        destinations=['simA'],  # you can specify multiple destinations destinations=['simA', 'simB'],
        payload_data=simulation_payload
    )
