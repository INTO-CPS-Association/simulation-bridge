# Use Matlab Agent

This Python module provides a simple RabbitMQ client to send simulation requests to a MATLAB agent and asynchronously listen for simulation results. It uses YAML configuration files for setup and supports sending payloads in YAML format over RabbitMQ messaging queues.

## Table of Contents

- [Use Matlab Agent](#use-matlab-agent)
  - [Table of Contents](#table-of-contents)
  - [Installation](#installation)
  - [Clients](#clients)
  - [Configuration](#configuration)
  - [Usage](#usage)
  - [Example](#example)
    - [Steps to run an example](#steps-to-run-an-example)
    - [Where to find the API payload files](#where-to-find-the-api-payload-files)
    - [Example usage](#example-usage)
  - [Control Commands](#control-commands)

## Installation

Before using this agent, ensure the required Python packages are installed:

```bash
pip install pika pyyaml
```

## Clients

Two Python scripts are provided:

- **use_matlab_agent.py** – Simple client that sends a simulation request and
  waits for results. Use this for _batch_ and _streaming_ simulations.
- **use_matlab_agent_interactive.py** – Async client for _interactive_
  simulations. It streams input frames to MATLAB and prints outputs as they
  arrive.

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

## Usage

Run the module as a standalone script to send simulation requests to the MATLAB agent and listen asynchronously for the results.
Command-Line Options:

- `--api-payload` (optional):  
  Specify the path to the YAML file containing the simulation request payload.

If this option is omitted, the script will look for a file named `simulation.yaml` in the default location as configured in `use.yaml` (by default in the same directory or as specified in the `simulation_request` field).

- **Without CLI option:**
  The script loads the simulation payload from the default path specified in `use.yaml`. This is by default a `simulation.yaml` file located in the working directory or as configured.

- **With CLI option:**
  You can override the default by specifying a custom path to the simulation payload YAML file using the `--api-payload` option.

For interactive simulations, use `use_matlab_agent_interactive.py` with the same
`--api-payload` flag. This client streams input frames based on the
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
    Execute the Python client with the appropriate API payload file:  
   python use_matlab_agent.py --api-payload "path_to_api_payload"

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

To run the batch simulation example, specify the full absolute path to the payload file when invoking the Python client:

```bash
python use_matlab_agent.py --api-payload "/Users/foo/simulation-bridge/agents/matlab/matlab_agent/docs/examples/batch-simulation/api/simulation_batch.yaml.example"
```

## Control Commands

During a simulation you can remotely control the MATLAB agent by sending simple
command messages via RabbitMQ. Supported commands are:

- `RUN` – clear any previous stop request and allow the simulation to run.
- `STOP` – request the currently running simulation to terminate gracefully.
- `CHECK` – query the agent status (returns `running` or `stopped`).

To issue a command, publish a YAML message containing a `command` field to the
agent input exchange:

```yaml
command: STOP
```
