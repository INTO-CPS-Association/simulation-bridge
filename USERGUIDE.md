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
  bridge_id: simulation_bridge

# RabbitMQ protocol adapter configuration
rabbitmq:
  host: localhost
  port: 5672
  vhost: /
  username: guest
  password: guest
  tls: false

  infrastructure:
    exchanges:
      - name: ex.input.bridge
        type: topic
        durable: true
        auto_delete: false
        internal: false

      - name: ex.bridge.output
        type: topic
        durable: true
        auto_delete: false
        internal: false

      - name: ex.sim.result
        type: topic
        durable: true
        auto_delete: false
        internal: false

      - name: ex.bridge.result
        type: topic
        durable: true
        auto_delete: false
        internal: false

    queues:
      - name: Q.bridge.input
        durable: true
        exclusive: false
        auto_delete: false

      - name: Q.bridge.result
        durable: true
        exclusive: false
        auto_delete: false

    bindings:
      - queue: Q.bridge.input
        exchange: ex.input.bridge
        routing_key: "#"

      - queue: Q.bridge.result
        exchange: ex.sim.result
        routing_key: "#"

# MQTT protocol adapter configuration
mqtt:
  host: localhost
  port: 1883
  keepalive: 60
  input_topic: bridge/input
  output_topic: bridge/output
  qos: 0
  username: guest
  password: guest
  tls: false

# REST protocol adapter configuration
rest:
  host: 0.0.0.0
  port: 5000
  endpoint: /message
  debug: false
  certfile: /certs/cert.pem
  keyfile: /certs/key.pem

# Logging configuration
logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: logs/sim_bridge.log
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

If you prefer to use `sim-bridge` as a standalone Python package, you can build and install it using the following steps:

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
