import yaml
import json
import paho.mqtt.client as mqtt

# Carica la configurazione
def load_config(config_path='config.yml'):
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

config = load_config()

broker = config['mqtt']['broker']
port = config['mqtt']['port']
input_topic = config['topics']['input_topic']
output_topic = config['topics']['output_topic']

# Callback per la connessione
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Connesso a {broker} con codice di stato {rc}")
    client.subscribe(input_topic)

# Callback per la ricezione dei messaggi
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        v1 = payload.get("value1", 1)
        v2 = payload.get("value2", 1)
        v3 = payload.get("value3", 1)
        product = v1 * v2 * v3
        print(f"Ricevuto: {payload} → Prodotto: {product}")

        result = {"product": product}
        client.publish(output_topic, json.dumps(result))
        print(f"Pubblicato su {output_topic}: {result}")
    except Exception as e:
        print(f"Errore nell'elaborazione del messaggio: {e}")

# Crea client MQTT
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.on_connect = on_connect
client.on_message = on_message

# Connessione al broker
client.connect(broker, port)

# Avvia il loop infinito
client.loop_forever()
