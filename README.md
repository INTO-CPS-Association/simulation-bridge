# Simulation Bridge

The **Simulation Bridge** is an open-source middleware solution designed to enable seamless and dynamic communication between Digital Twins (DT), Mock Physical Twins (MockPT), and their dedicated Simulator counterparts.
It serves as a **modular**, **reusable**, and **bidirectional** bridge, supporting multiple protocols and interaction modes to ensure interoperability across diverse simulation environments.

This framework supports multiple protocols and interaction modes, allowing for flexible integration and real-time control, monitoring, and data exchange in distributed simulation systems. By abstracting the communication layer, the Simulation Bridge simplifies running simulations remotely.

![Simulation Bridge Architecture](images/software_architecture.png)

## Table of Contents

- [Simulation Bridge](#simulation-bridge)
  - [Table of Contents](#table-of-contents)
  - [Key Features](#key-features)
    - [Multi-Protocol Support](#multi-protocol-support)
    - [Flexible Interaction Modes](#flexible-interaction-modes)
    - [Discoverability and Capability Registration](#discoverability-and-capability-registration)
    - [Data Transformation and Format Handling](#data-transformation-and-format-handling)
  - [Requirements](#requirements)
    - [1. Clone the Repository and Navigate to the Working Directory](#1-clone-the-repository-and-navigate-to-the-working-directory)
    - [2. Install Poetry and Create Virtual Environment](#2-install-poetry-and-create-virtual-environment)
    - [3. Install Project Dependencies](#3-install-project-dependencies)
    - [4. Install RabbitMQ](#4-install-rabbitmq)
      - [Option 1: Install RabbitMQ Locally](#option-1-install-rabbitmq-locally)
      - [Option 2: Use a Remote RabbitMQ Server](#option-2-use-a-remote-rabbitmq-server)
    - [5. Generate HTTPS Certificate](#5-generate-https-certificate)
  - [Usage](#usage)
    - [Getting Started](#getting-started)
      - [Running with the Default Configuration](#running-with-the-default-configuration)
      - [Running with a Custom Configuration File](#running-with-a-custom-configuration-file)
  - [Documentation](#documentation)
    - [Simulation Bridge](#simulation-bridge-1)
    - [Matlab Agent](#matlab-agent)
  - [Package Development](#package-development)
  - [License](#license)
  - [Author](#author)

## Key Features

### Multi-Protocol Support

The Simulation Bridge supports multiple communication protocols to ensure broad interoperability. RabbitMQ is provided as the default messaging layer, with support also available for MQTT and RESTful APIs. The architecture is extensible, allowing the integration of custom protocol adapters through a plugin interface.

### Flexible Interaction Modes

The system supports two primary modes of interaction, allowing for both discrete and continuous simulation workflows:

| Mode      | Description                                                                |
| --------- | -------------------------------------------------------------------------- |
| Batch     | Executes simulations in isolated runs, without the need for live feedback. |
| Streaming | Enables continuous data exchange for real-time monitoring and control.     |

### Discoverability and Capability Registration

Simulator capabilities are detected and registered automatically via a built-in agent system. This mechanism enables dynamic integration and reduces the need for manual configuration, improving scalability and adaptability across simulation environments.

### Data Transformation and Format Handling

Data exchanged between components can be automatically transformed across common formats including JSON, XML, and CSV. This transformation is handled in a protocol-agnostic manner, ensuring compatibility regardless of the source or target communication interface.

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

The Simulation Bridge requires an active RabbitMQ server. You can choose one of the following options:

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

#### 5. Generate HTTPS Certificate

To enable the REST Protocol Adapter and support HTTP/2.0, it is necessary to generate an HTTPS certificate.

````bash

```yaml
# Unique identifier for this simulation bridge instance
simulation_bridge:
  bridge_id: simulation_bridge # Must be unique if running multiple bridges

# Configuration for RabbitMQ protocol adapter
rabbitmq:
  host: localhost # RabbitMQ server hostname or IP
  port: 5672 # RabbitMQ port (default is 5672)
  virtual_host: / # RabbitMQ virtual host to use

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

# Configuration for REST protocol adapter
rest:
  host: 0.0.0.0 # Host IP to bind the REST server (0.0.0.0 = all interfaces)
  port: 5000 # Port to run the REST server
  input_endpoint: /message # Endpoint for receiving messages
  debug: false # Enable/disable Flask debug mode

  client:
    host: localhost # REST client target host
    port: 5001 # Port of the external REST receiver
    base_url: http://localhost:5001 # Base URL for outgoing REST requests
    output_endpoint: /result # Path for sending result messages

# Logging configuration
logging:
  level: INFO # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s" # Log format
  file: logs/sim_bridge.log # File path to store logs
````

## Usage

The Simulation Bridge requires a configuration file to run.

### Getting Started

**Generate a configuration file template:**

```bash
poetry run simulation-bridge --generate-config
```

This command creates a `config.yaml` file in your current directory. If the file already exists, it will not be overwritten. It will create a copy of `simulation_bridge/config/config.yaml.template`, which you can modify according to your environment.

#### Running with the Default Configuration

Once the configuration file is in place, start the Simulation Bridge with:

```bash
poetry run simulation-bridge
```

By default, the application looks for the configuration file at `simulation_bridge/config/config.yaml.template`.

#### Running with a Custom Configuration File

If you want to use a custom `config.yaml` file, run the `simulation-bridge` command with the `--config-file` or `-c` option followed by the path to your configuration file:

```bash
poetry run simulation-bridge --config-file <path_to_config.yaml>
```

Alternatively, you can use the shorthand `-c` option:

```bash
poetry run simulation-bridge -c <path_to_config.yaml>
```

## Documentation

### Simulation Bridge

- [🏗️ **Internal Architecture** ↗](simulation_bridge/docs/internal_architecture.md): Overview of the system's architecture, key modules, and their interactions.
- [🔌 **Extending with New Protocols** ↗](simulation_bridge/docs/adding_new_protocols.md): Instructions for integrating custom protocol adapters into the Simulation Bridge.

### Matlab Agent

- [🔗 **Matlab Agent** ↗](agents/matlab/README.md): Explanation of the MATLAB agent functionality and configuration.
- [⚙️ **Matlab Simulation Constraints** ↗](agents/matlab/matlab_agent/docs/README.md): A breakdown of the constraints and requirements for MATLAB-driven simulations.

## Package Development

The developer-specific commands are

```bash
pylint simulation_bridge
autopep8 --in-place --aggressive --recursive 'simulation_bridge'
```

## License

This project is licensed under the **INTO-CPS Association Public License v1.0**.  
See the [LICENSE](./LICENSE) file for full license text.

## Author

<div style="display: flex; flex-direction: column; gap: 25px;"> <!-- Marco Melloni --> <div style="display: flex; align-items: center; gap: 15px;"> <img src="images/melloni.jpg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/> <div> <h3 style="margin: 0;">Marco Melloni</h3> <p style="margin: 4px 0;">Digital Automation Engineering Student<br> University of Modena and Reggio Emilia, Department of Sciences and Methods for Engineering (DISMI)</p> <div> <a href="https://www.linkedin.com/in/marco-melloni/"> <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/> </a> <a href="https://github.com/marcomelloni" style="margin-left: 8px;"> <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/> </a> </div> </div> </div> <!-- Marco Picone --> <div style="display: flex; align-items: center; gap: 15px;"> <img src="images/picone.jpeg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/> <div> <h3 style="margin: 0;">Prof. Marco Picone</h3> <p style="margin: 4px 0;">Associate Professor<br> University of Modena and Reggio Emilia, Department of Sciences and Methods for Engineering (DISMI)</p> <div> <a href="https://www.linkedin.com/in/marco-picone-8a6a4612/"> <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/> </a> <a href="https://github.com/piconem" style="margin-left: 8px;"> <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/> </a> </div> </div> </div> <!-- Prasad Talasila --> <div style="display: flex; align-items: center; gap: 15px;"> <!-- Placeholder image --> <img src="images/talasila.jpeg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/> <div> <h3 style="margin: 0;">Dr. Prasad Talasila</h3> <p style="margin: 4px 0;">Postdoctoral Researcher<br> Aarhus University</p> <div> <a href="https://www.linkedin.com/in/prasad-talasila/"> <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/> </a> <a href="https://github.com/prasadtalasila" style="margin-left: 8px;"> <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/> </a> </div> </div> </div> </div>
