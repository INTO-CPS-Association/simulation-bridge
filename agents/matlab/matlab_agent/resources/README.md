# Use Matlab Agent

This Python module provides a simple RabbitMQ client to send simulation requests to a MATLAB agent and asynchronously listen for simulation results. It uses YAML configuration files for setup and supports sending payloads in YAML format over RabbitMQ messaging queues.

## Table of Contents

- [Use Matlab Agent](#use-matlab-agent)
  - [Table of Contents](#table-of-contents)
  - [Installation](#installation)
  - [Clients](#clients)
  - [Configuration](#configuration)
  - [Usage](#usage)
    - [Command-line options](#command-line-options)
  - [Example](#example)
    - [Steps to run an example](#steps-to-run-an-example)
    - [Where to find the API payload files](#where-to-find-the-api-payload-files)
    - [Example usage](#example-usage)

## Installation

It is recommended to run the examples in an isolated Python environment and
install the required dependencies:

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # On Windows use: .\.venv\Scripts\activate

# Install dependencies
pip install pika pyyaml anyio aio-pika
```

The `pika` and `aio-pika` libraries provide RabbitMQ clients for the synchronous
and asynchronous examples respectively, while `anyio` and `pyyaml` handle file
I/O and YAML parsing.

## Clients

Three Python scripts are provided, each matching a different simulation mode:

- **use_matlab_agent_batch.py** – Executes a _batch_ simulation and waits until
  the final results are returned before terminating.
- **use_matlab_agent_streaming.py** – Starts a _streaming_ simulation where
  outputs are continuously printed as they arrive.
- **use_matlab_agent_interactive.py** – Asynchronous client for
  _interactive_ simulations. It streams input frames to MATLAB and handles
  real-time results.

## Configuration

The agent requires a configuration file (`use.yaml`) to set up RabbitMQ connection parameters and specify the path to the simulation request payload.

Example `use.yaml` content:

```yaml
rabbitmq:
  host: localhost # RabbitMQ server hostname or IP address
  port: 5672 # RabbitMQ server port
  username: guest # RabbitMQ username
  password: guest # RabbitMQ password
  heartbeat: 600 # Heartbeat interval in seconds
  vhost: / # RabbitMQ virtual host

simulation_request: ../api/simulation.yaml # Default path to the simulation YAML payload
```

The MATLAB wrapper classes also read their configuration from a
`config/default.yaml` file. A template named `default.yaml.template` is
distributed with the agent under `config/`. When you run
`matlab-agent --generate-project`, this template is copied to
`config/default.yaml`, which the wrappers use at runtime.

## Usage

Run any of the client scripts below to send a simulation request and listen for
results. Each script exposes the same interface:

```bash
python use_matlab_agent_batch.py --api-payload /path/to/payload.yaml
python use_matlab_agent_streaming.py --api-payload /path/to/payload.yaml
python use_matlab_agent_interactive.py --api-payload /path/to/payload.yaml
```

### Command-line options

- `--api-payload` (optional): path to the YAML simulation request. If omitted,
  the script loads `simulation.yaml` from the default location configured in
  `use.yaml`.

The interactive client streams input frames based on the
`inputs.stream_source` field and prints outputs as they arrive.

## Example

In the directory  
`/Users/foo/simulation-bridge/agents/matlab/matlab_agent/docs/examples`  
you will find several folders containing practical examples. Each example folder includes a `README.md` with detailed instructions:

- [Streaming Simulation](../docs/examples/streaming-simulation/README.md)
- [Interactive Simulation](../docs/examples/interactive-simulation/README.md)
- [Batch Simulation](../docs/examples/batch-simulation/README.md)
- [Industrial Cooling Fan Anomaly Detection](../docs/examples/industrial-cooling-fan-anomaly-detection/README.md)

### Steps to run an example

1. **Configure the simulation request path**  
   Edit the `config.yaml` file inside the MATLAB agent folder to set the path to the simulation request folder you want to use. This path should point to the example you want to run.

2. **Run the MATLAB agent**  
   Start the MATLAB agent so it is ready to receive simulation requests.

3. **Send a simulation request using the Python client**
   Run the client that matches your simulation mode and provide the path to the
   API payload:

   ```bash
   python use_matlab_agent_batch.py --api-payload '/abs/path/to/batch_payload.yaml'
   python use_matlab_agent_streaming.py --api-payload '/abs/path/to/streaming_payload.yaml'
   python use_matlab_agent_interactive.py --api-payload '/abs/path/to/interactive_payload.yaml'
   ```

> **Note:** It is recommended to use absolute paths when specifying the `--api-payload` argument to avoid path resolution issues. It is a good practice to place the path in single quotes.

### Where to find the API payload files

Each example folder contains an `api/` subfolder with example simulation payload YAML files. Use these as the `--api-payload` argument when running the Python client. For instance:

- Industrial Cooling Fan Anomaly Detection:  
  `docs/examples/industrial-cooling-fan-anomaly-detection/api/simulation_anomaly_detection.yaml.example`

- Batch Simulation:  
  `docs/examples/batch-simulation/api/simulation_batch.yaml.example`

- Streaming Simulation:
  `docs/examples/streaming-simulation/api/simulation_streaming.yaml.example`

- Interactive Simulation:
  `docs/examples/interactive-simulation/api/simulation_interactive.yaml.example`

### Example usage

Run the client script that matches the example you want to execute. Use absolute
paths to avoid resolution issues.

- **Batch simulation**

  ```bash
  python use_matlab_agent_batch.py --api-payload "/Users/foo/simulation-bridge/agents/matlab/matlab_agent/docs/examples/batch-simulation/api/simulation_batch.yaml.example"
  ```

- **Streaming simulation**

  ```bash
  python use_matlab_agent_streaming.py --api-payload "/Users/foo/simulation-bridge/agents/matlab/matlab_agent/docs/examples/streaming-simulation/api/simulation_streaming.yaml.example"
  ```

- **Interactive simulation**

  ```bash
  python use_matlab_agent_interactive.py --api-payload "/Users/foo/simulation-bridge/agents/matlab/matlab_agent/docs/examples/interactive-simulation/api/simulation_interactive.yaml.example"
  ```
