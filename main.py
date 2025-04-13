import yaml
import paho.mqtt.client as mqtt
import json
from typing import Dict, Any

def load_config(config_path: str = 'config.yml') -> Dict[str, Any]:
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

config = load_config()

# Configurazione MQTT
broker = config['mqtt']['broker']
port = config['mqtt']['port']
timeout = config.get('timeout', 10)
simulations = config['simulations']

# Inizializzazione client
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connesso con successo al broker MQTT!")
        
        # Sottoscrizione a tutti i topic di output
        for sim_name, sim_config in simulations.items():
            client.subscribe(sim_config['output_topic'])
            print(f"Sottoscritto a: {sim_config['output_topic']}")
        
        # Invio dati a tutti i topic di input
        data = {
            "value1": 3.5,
            "value2": 2.1,
            "value3": 4.7
        }
        
        for sim_name, sim_config in simulations.items():
            client.publish(sim_config['input_topic'], json.dumps(data))
            print(f"Inviato a {sim_name} ({sim_config['input_topic']})")
    else:
        print(f"Connessione fallita: {reason_code}")

def on_message(client, userdata, msg):
    # Identifica la simulazione dal topic
    simulator = next(
        (sim_name for sim_name, sim_config in simulations.items() 
         if msg.topic == sim_config['output_topic']),
        None
    )
    
    if simulator:
        print(f"\nRisultato da {simulator.upper()} ({msg.topic}):")
    else:
        print(f"\nRicevuto da topic sconosciuto: {msg.topic}")
    
    try:
        payload = json.loads(msg.payload.decode())
        print(json.dumps(payload, indent=4))
    except json.JSONDecodeError:
        print(msg.payload.decode())

# Assegnazione callback
client.on_connect = on_connect
client.on_message = on_message

# Connessione e loop
client.connect(broker, port, timeout)
print(f"Connessione a {broker}:{port}...")
client.loop_forever()