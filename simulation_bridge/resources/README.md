## Example Clients

This folder contains four example clients that communicate with the Simulation Bridge using different protocols:

- **mqtt/** – MQTT Client
- **rabbitmq/** – RabbitMQ Client
- **rest/** – REST Client
- **inmemory/** – In-Memory Client

Each client is completely independent and demonstrates how to send a simulation request and handle real-time responses.

### Folder Structure

```
client/
├── README.md               # you are here!
├── simulation.yaml         # API payload for simulation requests
├── mqtt/
│   ├── mqtt_client.py      # MQTT-specific Python client
│   ├── mqtt_use.yaml       # MQTT client configuration
│   └── requirements.txt    # Python dependencies
├── rabbitmq/
│   ├── rabbitmq_client.py  # RabbitMQ-specific Python client
│   ├── rabbitmq_use.yaml   # RabbitMQ client configuration
│   └── requirements.txt    # Python dependencies
├── rest/
│   ├── rest_client.py      # REST-specific Python client
│   ├── rest_use.yaml       # REST client configuration
│   └── requirements.txt    # Python dependencies
└── inmemory/
    ├── inmemory_client.py  # In-memory simulation client
    ├── inmemory_use.yaml   # In-memory client configuration
    └── requirements.txt    # Python dependencies
```

Each subfolder (mqtt/, rabbitmq/, rest/, inmemory/) contains:

- `*_client.py` – Protocol-specific Python client
- `*_use.yaml` – Client configuration file (network parameters, authentication, etc.)
- `requirements.txt` – Python dependencies to run the client

Additionally, in the root folder (client/) there is:

- `simulation.yaml` – The API payload to use for making requests to the simulation bridge

> **Note:** Make sure you have agents and simulation bridge configured and running before using any client.

### How to use a client

#### 1. Configure API payload

Customize the `client/simulation.yaml` file with your distributed simulation parameters.

#### 2. Configure the client

In the subfolder of the client you want to use, modify `mqtt_use.yaml`, `rabbitmq_use.yaml`, `rest_use.yaml` or `inmemory_use.yaml` based on the chosen protocol (e.g. host, port, topic, URL, etc.).

#### 3. Install dependencies

Navigate to the desired client folder, for example:

```bash
cd mqtt
pip install -r requirements.txt
```

#### 4. Run the client

Execute the Python script to send the request and start listening for responses:

```bash
python mqtt_client.py
```

Each client will send the request defined in `simulation.yaml` and remain listening to receive results.

### Customization

These clients are examples designed to be adapted. You can modify them to:

- Integrate into your workflows
- Automate decisions based on simulation results
- Log or save results
- Handle asynchronous simulation flows
