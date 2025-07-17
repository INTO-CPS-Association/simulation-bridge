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

Requests must follow the standard simulation schema:

```yaml
simulation:
  request_id: abcdef12345
  # (RequestID) to identify each request.

  client_id: dt
  # Unique identifier of the sender of this simulation request

  simulator: matlab
  # Specifies the target system for the simulation.
  # Use 'matlab' to route the request to the MATLAB simulator.

  type: streaming
  # Specifies the simulation execution mode.
  # Options:
  #   - 'batch': runs the simulation in batch mode, where results are returned only after the entire computation is complete.
  #   - 'streaming': runs the simulation in streaming mode, providing real-time updates at each computation step.

  timestamp: "2024-01-01T00:00:00Z" # Timestamp for the simulation request in ISO 8601 format

  timeout: 30 # Timeout in seconds for the simulation request.

  file: SimulationStreaming.m
  # The name of the MATLAB script or function file to execute for this simulation.

  inputs:
    # Input variables to be passed to the simulation.
    # Customize these key-value pairs as needed for your specific simulation.
    i1: ..
    i2: ..
    i3: ..

  outputs:
    # Expected output variables from the simulation.
    # Customize these keys based on what outputs your simulation provides.
    o1: ..
    o2: ..
    o3: ..
    o4: ..
```

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
