import pika
import yaml

# Funzione per caricare i dati dal file YAML
def load_simulation_data(filename):
    with open(filename, 'r') as file:
        data = yaml.safe_load(file)
    return data

# Connessione a RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Dichiarazione della coda per inviare i dati
channel.queue_declare(queue='queue_1')

# Funzione per inviare i dati come messaggio
def send_message(data):
    message = yaml.dump(data)  # Convertiamo i dati in formato YAML per inviarli come messaggio
    print(f"Invio messaggio: {message}")
    channel.basic_publish(exchange='',
                          routing_key='queue_1',
                          body=message)

# Carica i dati dal file YAML
filename = 'simulation.yml'
simulation_data = load_simulation_data(filename)

# Invia i dati caricati
send_message(simulation_data)

# Funzione per ricevere la risposta con i risultati dalla coda 'queue_2'
def on_response(ch, method, properties, body):
    print(f"Ricevuto dal client 2 (risultati della simulazione): {body.decode()}")
    # Non chiudiamo la connessione subito, possiamo lasciare il programma in ascolto per ricevere più risposte

# Impostazione del consumer per ricevere la risposta da 'queue_2'
channel.queue_declare(queue='queue_2')  # Assicurati che la coda 'queue_2' sia dichiarata
channel.basic_consume(queue='queue_2', on_message_callback=on_response, auto_ack=False)

# Avvia la connessione per ascoltare i risultati
print("In ascolto dei risultati sulla coda 'queue_2'...")
channel.start_consuming()

# Il programma ora rimarrà in ascolto su 'queue_2' finché non verrà fermato manualmente
