# User Guide

This guide outlines how to configure and execute the simulation-bridge application. It provides detailed information on the configuration parameters, command-line options, and execution procedures.

- [User Guide](#user-guide)
  - [Requirements](#requirements)
    - [1. Clone the Repository and Navigate to the Working Directory](#1-clone-the-repository-and-navigate-to-the-working-directory)
    - [2. Install Poetry and Create Virtual Environment](#2-install-poetry-and-create-virtual-environment)
    - [3. Install Project Dependencies](#3-install-project-dependencies)
    - [4. Install RabbitMQ](#4-install-rabbitmq)
      - [Option 1: Install RabbitMQ Locally](#option-1-install-rabbitmq-locally)
      - [Option 2: Use a Remote RabbitMQ Server](#option-2-use-a-remote-rabbitmq-server)
  - [Configuration](#configuration)
  - [Usage](#usage)
    - [Generating a Template](#generating-a-template)
    - [Running with the Default Configuration](#running-with-the-default-configuration)
    - [Running with a Custom Configuration File](#running-with-a-custom-configuration-file)
  - [Command-Line Options](#command-line-options)

## Requirements

#### 1. Clone the Repository and Navigate to the Working Directory

```bash
git clone https://github.com/INTO-CPS-Association/simulation-bridge.git
cd simulation-bridge
```

#### 2. Install Poetry and Create Virtual Environment

Ensure that Poetry is installed on your system. If it is not already installed, execute the following commands:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install poetry
```

Verify the installation by checking the Poetry version:

```bash
poetry --version
```

Activate the virtual environment:

```bash
poetry env activate
```

> **Important:**  
> The command `poetry env activate` does not automatically activate the virtual environment; instead, it prints the command you need to run to activate it.  
> You must copy and paste the displayed command, for example:

```bash
source /path/to/virtualenv/bin/activate
```

Verify that the environment is active by checking the Python path:

```bash
which python
```

#### 3. Install Project Dependencies

Run the following command to install all dependencies defined in `pyproject.toml`:

```bash
poetry install
```

#### 4. Install RabbitMQ

The _sim-bridge_ requires an active RabbitMQ server. You can choose one of the following options:

##### Option 1: Install RabbitMQ Locally

If you do not have access to an external RabbitMQ server, you can install one locally. On macOS, use Homebrew:

```bash
brew update
brew install rabbitmq
brew services start rabbitmq
```

Verify that RabbitMQ is running:

```bash
brew services list
rabbitmqctl status
lsof -i :5672
```

##### Option 2: Use a Remote RabbitMQ Server

Alternatively, connect to an existing RabbitMQ instance hosted on a remote server (on-premise or cloud).

## Configuration

The simulation-bridge uses a YAML-based configuration file. Below is a comprehensive example including all supported protocol adapters and logging options:

```yaml
# Unique identifier for this simulation bridge instance
simulation_bridge:
  bridge_id: simulation_bridge # Must be unique if running multiple bridges

# Configuration for RabbitMQ protocol adapter
rabbitmq:
  host: localhost # RabbitMQ server hostname or IP
  port: 5672 # RabbitMQ port (default is 5672)
  vhost: / # RabbitMQ virtual host to use
  username: guest # Username
  password: guest # Password

  infrastructure:
    exchanges:
      # Define all the exchanges used by the bridge
      - name: ex.input.bridge # Incoming messages from clients
        type: topic # Exchange type (topic allows routing via routing keys)
        durable: true # Should survive RabbitMQ restarts
        auto_delete: false # Should not be deleted when unused
        internal: false # Accessible to clients

      - name: ex.bridge.output # Messages forwarded to simulator
        type: topic
        durable: true
        auto_delete: false
        internal: false

      - name: ex.sim.result # Results from simulator
        type: topic
        durable: true
        auto_delete: false
        internal: false

      - name: ex.bridge.result # Final result for clients
        type: topic
        durable: true
        auto_delete: false
        internal: false

    queues:
      # Queues for consuming messages
      - name: Q.bridge.input # Bridge input queue
        durable: true # Should survive server restarts
        exclusive: false # Can be shared by multiple consumers
        auto_delete: false # Should not be deleted automatically

      - name: Q.bridge.result # Queue for receiving simulation results
        durable: true
        exclusive: false
        auto_delete: false

    bindings:
      # Bind queues to exchanges using routing keys
      - queue: Q.bridge.input
        exchange: ex.input.bridge
        routing_key: "#" # Receive all messages (wildcard)

      - queue: Q.bridge.result
        exchange: ex.sim.result
        routing_key: "#" # Receive all messages (wildcard)

# Configuration for MQTT protocol adapter
mqtt:
  host: localhost # MQTT broker host
  port: 1883 # MQTT port (default is 1883)
  keepalive: 60 # Keepalive interval in seconds
  input_topic: bridge/input # Topic to subscribe to for input
  output_topic: bridge/output # Topic to publish results
  qos: 0 # Quality of Service level (0: at most once)
  username: guest # Username
  password: guest # Password

# Configuration for REST protocol adapter
rest:
  host: 0.0.0.0 # Host IP to bind the REST server (0.0.0.0 = all interfaces)
  port: 5000 # Port to run the REST server
  endpoint: /message # Endpoint for receiving messages
  debug: false # Enable/disable Flask debug mode
  certfile: /certs/certfile.pem # Path to the SSL certificate file
  keyfile: /certs/keyfile.pem # Path to the SSL private key file

# Logging configuration
logging:
  level: INFO # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s" # Log format
  file: logs/sim_bridge.log # File path to store logs
```

Each section of the configuration file enables or customizes a specific protocol adapter used to receive and dispatch simulation messages.

> **Note:** The certificate file `certfile.pem` and the key file `keyfile.pem` will be automatically created by the _sim-bridge_, even if they are missing or invalid.

## Usage

The simulation-bridge requires a valid configuration file to operate.

### Generating a Template

To create a default configuration file:

```bash
poetry run simulation-bridge --generate-config
```

This command generates a `config.yaml` file in the current working directory based on the template located at `simulation_bridge/config/config.yaml.template`.
If the file already exists, it will not be overwritten.

### Running with the Default Configuration

Once the configuration is in place, the bridge can be launched with:

```bash
poetry run simulation-bridge
```

By default, the application attempts to load the configuration from `simulation_bridge/config/config.yaml.template`.

**Note:** To facilitate debugging during development, set `logging.level` to `DEBUG`.

### Running with a Custom Configuration File

To specify a custom configuration file, use the `--config-file` (or `-c`) option:

```bash
poetry run simulation-bridge --config-file /path/to/config.yaml
```

Alternatively, use the shorthand syntax:

```bash
poetry run simulation-bridge -c /path/to/config.yaml
```

## Command-Line Options

| Option                | Description                                                     |
| --------------------- | --------------------------------------------------------------- |
| `--generate-config`   | Generates a default configuration file in the current directory |
| `--config-file`, `-c` | Path to a custom configuration file                             |
| `--help`, `-h`        | Displays help information for available options                 |
