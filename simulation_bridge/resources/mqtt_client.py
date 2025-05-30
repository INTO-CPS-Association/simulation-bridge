import paho.mqtt.client as mqtt
import json
import time
import yaml
import os

# Configurazione MQTT
MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60
MQTT_INPUT_TOPIC = "bridge/input"
MQTT_OUTPUT_TOPIC = "bridge/output"
MQTT_QOS = 0

# Callback per la ricezione dei messaggi
def on_message(client, userdata, msg):
    print("\n📥 Messaggio ricevuto:")
    print(f"🔹 Topic: {msg.topic}")
    print(f"🔹 Payload: {msg.payload.decode()}")

def send_message_and_listen():
    # Carica il file YAML
    file_path = os.path.join(os.path.dirname(__file__), 'simulation.yaml')
    try:
        with open(file_path, 'r') as file:
            payload = yaml.safe_load(file)
            print("✅ Payload caricato:", payload)
    except Exception as e:
        print(f"❌ Errore nel caricamento di simulation.yaml: {e}")
        return

    client = mqtt.Client()

    # Configura callback per i messaggi ricevuti
    client.on_message = on_message

    # Connessione al broker MQTT
    client.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)

    # Iscrizione al topic di output
    client.subscribe(MQTT_OUTPUT_TOPIC, qos=MQTT_QOS)

    # Pubblica il messaggio su bridge/input
    client.publish(MQTT_INPUT_TOPIC, json.dumps(payload), qos=MQTT_QOS)
    print(f"📤 Messaggio pubblicato su {MQTT_INPUT_TOPIC}")

    # Inizia il loop per ricevere messaggi
    print(f"📡 In ascolto su {MQTT_OUTPUT_TOPIC}...\n(CTRL+C per terminare)")
    client.loop_forever()

if __name__ == "__main__":
    send_message_and_listen()
