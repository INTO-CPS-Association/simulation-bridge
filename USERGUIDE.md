# User Guide

This guide outlines how to configure and execute the _sim-bridge_ application. It provides detailed information on the configuration parameters, command-line options, and execution procedures.

## Table of Contents

- [User Guide](#user-guide)
  - [Table of Contents](#table-of-contents)
  - [Requirements](#requirements)
    - [Clone the Repository](#clone-the-repository)
    - [Install Poetry and Create Virtual Environment](#install-poetry-and-create-virtual-environment)
    - [Install Project Dependencies](#install-project-dependencies)
    - [Install RabbitMQ](#install-rabbitmq)
      - [Option 1: Install RabbitMQ Locally](#option-1-install-rabbitmq-locally)
      - [Option 2: Use a Remote RabbitMQ Server](#option-2-use-a-remote-rabbitmq-server)
  - [Configuration](#configuration)
  - [Usage](#usage)
    - [Generating a Template Configuration](#generating-a-template-configuration)
    - [Generating a Complete Project Structure](#generating-a-complete-project-structure)
    - [Running with Default Configuration](#running-with-default-configuration)
    - [Running with Custom Configuration](#running-with-custom-configuration)
  - [Use _sim-bridge_ as a Pip-Installable Package](#use-sim-bridge-as-a-pip-installable-package)
    - [Build the Package](#build-the-package)
    - [Install the Package](#install-the-package)
    - [Use the Package](#use-the-package)
  - [Command-Line Options Overview](#command-line-options-overview)
  - [Author](#author)

## Requirements

### Clone the Repository

```bash
git clone https://github.com/INTO-CPS-Association/simulation-bridge.git
cd simulation-bridge
```

### Install Poetry and Create Virtual Environment

Ensure Poetry is installed on your system:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install poetry
```

Verify the installation:

```bash
poetry --version
```

Activate the virtual environment:

```bash
poetry env activate
```

> **Important:** The `poetry env activate` command prints the activation command. Copy and run the displayed command:
>
> ```bash
> source /path/to/virtualenv/bin/activate
> ```

Verify the environment is active:

```bash
which python
```

### Install Project Dependencies

Install all dependencies defined in `pyproject.toml`:

```bash
poetry install
```

### Install RabbitMQ

The _sim-bridge_ requires an active RabbitMQ server. Choose one of the following options:

#### Option 1: Install RabbitMQ Locally

On macOS using Homebrew:

```bash
brew update
brew install rabbitmq
brew services start rabbitmq
```

Verify RabbitMQ is running:

```bash
brew services list
rabbitmqctl status
lsof -i :5672
```

#### Option 2: Use a Remote RabbitMQ Server

Connect to an existing RabbitMQ instance hosted on a remote server.

## Configuration

The _sim-bridge_ uses a YAML-based configuration file. Below is a comprehensive example:

```yaml
# Unique identifier for this simulation bridge instance
simulation_bridge:
  bridge_id: simulation_bridge # ID used to identify this instance of the sim-bridge

# RabbitMQ protocol adapter configuration
rabbitmq:
  host: localhost # RabbitMQ broker hostname or IP address
  port: 5672 # Port for non-TLS AMQP connections (default: 5672)
  vhost: / # Virtual host used in RabbitMQ
  username: guest # Username for RabbitMQ authentication
  password: guest # Password for RabbitMQ authentication
  tls: false # Whether to use TLS (amqps) or not

  infrastructure:
    exchanges:
      - name: ex.input.bridge # Exchange for receiving input messages from external systems
        type: topic # Exchange type (topic allows pattern-based routing)
        durable: true # Exchange survives broker restarts
        auto_delete: false # Exchange won't be deleted when no longer used
        internal: false # Exchange is available to external producers

      - name: ex.bridge.output # Exchange for sending output messages to external systems
        type: topic
        durable: true
        auto_delete: false
        internal: false

      - name: ex.sim.result # Exchange for simulation result messages
        type: topic
        durable: true
        auto_delete: false
        internal: false

      - name: ex.bridge.result # Exchange for bridge-processed results
        type: topic
        durable: true
        auto_delete: false
        internal: false

    queues:
      - name: Q.bridge.input # Queue for receiving messages intended for the bridge
        durable: true # Queue survives broker restarts
        exclusive: false # Queue is not exclusive to one connection
        auto_delete: false # Queue will not be deleted automatically

      - name: Q.bridge.result # Queue for receiving simulation results
        durable: true
        exclusive: false
        auto_delete: false

    bindings:
      - queue: Q.bridge.input # Bind the input queue...
        exchange: ex.input.bridge # ...to this exchange...
        routing_key: "#" # ...with wildcard routing (all messages)

      - queue: Q.bridge.result # Bind the result queue...
        exchange: ex.sim.result # ...to receive all simulation result messages
        routing_key: "#" # ...with wildcard routing

# MQTT protocol adapter configuration
mqtt:
  host: localhost # MQTT broker hostname or IP
  port: 1883 # Port for MQTT (1883 for non-TLS, 8883 for TLS)
  keepalive: 60 # Keep-alive interval in seconds for MQTT client
  input_topic: bridge/input # Topic to subscribe to for receiving messages
  output_topic: bridge/output # Topic to publish processed messages to
  qos: 0 # Quality of Service level (0 = at most once)
  username: guest # Username for MQTT authentication
  password: guest # Password for MQTT authentication
  tls: false # Whether to use secure MQTT (mqtts) or not

# REST protocol adapter configuration
rest:
  host: 0.0.0.0 # REST API binds to all network interfaces
  port: 5000 # Port for RESTful HTTP server
  endpoint: /message # Endpoint path for sending messages to the bridge
  debug: false # Disable Flask debug mode (set to true for development)
  certfile: certs/cert.pem # Path to the TLS certificate file for HTTPS
  keyfile: certs/key.pem # Path to the private key file for HTTPS

# Logging configuration
logging:
  level: INFO # Logging level (e.g., DEBUG, INFO, WARNING, ERROR)
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s" # Format of log messages
  file: logs/sim_bridge.log # Path to the log output file
```

> **Note:** Certificate files (`certfile.pem` and `keyfile.pem`) will be automatically created by the _sim-bridge_ if missing.

## Usage

### Generating a Template Configuration

Create a default configuration file:

```bash
poetry run simulation-bridge --generate-config
```

This generates a `config.yaml` file in the current directory. Existing files will not be overwritten.

### Generating a Complete Project Structure

Generate a complete example project with clients and configurations:

```bash
poetry run simulation-bridge --generate-project
```

This creates the following structure:

```
.
├── config.yaml                     # Main configuration file
├── client/
│   ├── README.md                   # Client documentation
│   ├── simulation.yaml             # Example simulation payload
│   ├── mqtt/
│   │   ├── mqtt_client.py          # MQTT client implementation
│   │   ├── mqtt_use.yaml           # MQTT usage configuration
│   │   └── requirements.txt        # MQTT client requirements
│   ├── rabbitmq/
│   │   ├── rabbitmq_client.py      # RabbitMQ client implementation
│   │   ├── rabbitmq_use.yaml       # RabbitMQ usage configuration
│   │   └── requirements.txt        # RabbitMQ client requirements
│   └── rest/
│       ├── rest_client.py          # REST client implementation
│       ├── rest_use.yaml           # REST usage configuration
│       └── requirements.txt        # REST client requirements
```

### Running with Default Configuration

Launch the bridge with the default configuration:

```bash
poetry run simulation-bridge
```

The application loads configuration from `simulation-bridge/config.yaml` by default.

### Running with Custom Configuration

Specify a custom configuration file:

```bash
poetry run simulation-bridge --config-file /path/to/config.yaml
```

Or use the shorthand syntax:

```bash
poetry run simulation-bridge -c /path/to/config.yaml
```

## Use _sim-bridge_ as a Pip-Installable Package

If you prefer to use `simulation-bridge` as a standalone Python package, you can build and install it using the following steps:

### Build the Package

In the root of the project (where `pyproject.toml` is located), run:

```bash
poetry build
```

This will generate the distribution files in the `dist/` directory:

- `simulation_bridge-<version>.tar.gz`
- `simulation_bridge-<version>-py3-none-any.whl`

### Install the Package

You can install the built package using pip:

```bash
pip install dist/simulation_bridge-<version>-py3-none-any.whl
```

Replace `<version>` with the actual version number (e.g., `0.1.0`).

### Use the Package

After installation, the `simulation-bridge` command will be available globally in your environment:

```bash
simulation-bridge --help
```

You can use it exactly as described in the previous sections:

```bash
simulation-bridge --generate-config
simulation-bridge --config-file config.yaml
```

> **Note:** When using the installed package, you no longer need to prefix commands with `poetry run`.

## Command-Line Options Overview

| Option                | Description                                                          |
| --------------------- | -------------------------------------------------------------------- |
| `--generate-config`   | Generates a default configuration file in the current directory      |
| `--generate-project`  | Generates a sample project with clients, configs, and usage examples |
| `--config-file`, `-c` | Path to a custom configuration file                                  |
| `--help`, `-h`        | Displays help information for available options                      |

## Author

<div style="display: flex; flex-direction: column; gap: 25px;"> <!-- Marco Melloni --> <div style="display: flex; align-items: center; gap: 15px;"> <img src="images/melloni.jpg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/> <div> <h3 style="margin: 0;">Marco Melloni</h3> <p style="margin: 4px 0;">Digital Automation Engineering Student<br> University of Modena and Reggio Emilia, Department of Sciences and Methods for Engineering (DISMI)</p> <div> <a href="https://www.linkedin.com/in/marco-melloni/"> <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/> </a> <a href="https://github.com/marcomelloni" style="margin-left: 8px;"> <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/> </a> </div> </div> </div> <!-- Marco Picone --> <div style="display: flex; align-items: center; gap: 15px;"> <img src="images/picone.jpeg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/> <div> <h3 style="margin: 0;">Prof. Marco Picone</h3> <p style="margin: 4px 0;">Associate Professor<br> University of Modena and Reggio Emilia, Department of Sciences and Methods for Engineering (DISMI)</p> <div> <a href="https://www.linkedin.com/in/marco-picone-8a6a4612/"> <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/> </a> <a href="https://github.com/piconem" style="margin-left: 8px;"> <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/> </a> </div> </div> </div> <!-- Prasad Talasila --> <div style="display: flex; align-items: center; gap: 15px;"> <!-- Placeholder image --> <img src="images/talasila.jpeg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/> <div> <h3 style="margin: 0;">Dr. Prasad Talasila</h3> <p style="margin: 4px 0;">Postdoctoral Researcher<br> Aarhus University</p> <div> <a href="https://www.linkedin.com/in/prasad-talasila/"> <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/> </a> <a href="https://github.com/prasadtalasila" style="margin-left: 8px;"> <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/> </a> </div> </div> </div> </div>
