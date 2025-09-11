# AnyLogic agent

The AnyLogic Agent is a Python-based connector that integrates AnyLogic simulations with the Simulation Bridge. It:

- Connects to RabbitMQ to receive simulation requests and publish results.
- Starts a UDP listener to receive live data from an AnyLogic model and forward it to the Bridge.

This agent is designed to work with the Simulation Bridge but can be used standalone with RabbitMQ. All parameters are configured via a YAML file.

## Table of Contents

- [AnyLogic agent](#anylogic-agent)
  - [Table of Contents](#table-of-contents)
  - [Demo Video](#demo-video)
  - [Requirements](#requirements)
    - [Installation](#installation)
      - [1. Clone the Repository](#1-clone-the-repository)
      - [2. Install Poetry and Create Virtual Environment](#2-install-poetry-and-create-virtual-environment)
      - [3. Install Project Dependencies](#3-install-project-dependencies)
    - [Configuration](#configuration)
  - [Usage](#usage)
    - [Generate a Config](#generate-a-config)
    - [Run the Agent](#run-the-agent)
  - [Distribute as a PIP Package](#distribute-as-a-pip-package)
    - [Verify the Package](#verify-the-package)
    - [Release a New Version](#release-a-new-version)
  - [Quick Start: Client Interaction](#quick-start-client-interaction)
  - [Workflow](#workflow)
  - [Package Development](#package-development)
  - [Author](#author)

## Demo Video

Short demo of the first AnyLogic ↔ Bridge integration:

- [Watch the video (MP4)](anylogic_agent/images/anylogic-bridge-first-implementation.mp4)

## Requirements

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/INTO-CPS-Association/simulation-bridge.git
cd simulation-bridge
cd agents/anylogic
```

#### 2. Install Poetry and Create Virtual Environment

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install poetry
poetry --version

# Activate the environment (run the path shown)
poetry env activate
```

Verify the active Python:

```bash
which python
```

#### 3. Install Project Dependencies

```bash
poetry install
```

### Configuration

The agent reads a YAML config. Start from the template at `anylogic_agent/config/config.yaml.template`.

Key fields overview:

```yaml
agent:
  agent_id: anylogic # Unique agent identifier
  simulator: anylogic # Simulator name

rabbitmq:
  host: localhost # RabbitMQ host
  port: 5672 # RabbitMQ port
  username: guest # Credentials
  password: guest
  heartbeat: 600 # Heartbeat seconds
  vhost: / # Virtual host
  tls: false # Enable TLS if needed

simulation:
  path: /path/to/examples # Folder containing AnyLogic models/files

exchanges:
  input: ex.bridge.output # Commands exchange
  output: ex.sim.result # Results exchange

queue:
  durable: true # Durable queues
  prefetch_count: 1 # Prefetch setting

logging:
  level: INFO # DEBUG, INFO, ERROR
  file: logs/anylogic_agent.log

udp:
  host: localhost # UDP listener host
  port: 9876 # UDP listener port

response_templates:
  success:
    status: success
    simulation:
      type: batch
    timestamp_format: "%Y-%m-%dT%H:%M:%SZ"
    include_metadata: true
    metadata_fields: [execution_time, memory_usage]

  error:
    status: error
    include_stacktrace: false
    error_codes:
      invalid_config: 400
      execution_error: 500
      timeout: 504
      missing_file: 404
    timestamp_format: "%Y-%m-%dT%H:%M:%SZ"

  progress:
    status: in_progress
    include_percentage: true
    update_interval: 5
    timestamp_format: "%Y-%m-%dT%H:%M:%SZ"
```

Notes:

- UDP is used for inbound data from the AnyLogic model. TCP/performance settings are not used in this agent.
- RabbitMQ exchanges are `ex.bridge.output` (input/commands) and `ex.sim.result` (output/results).

## Usage

### Generate a Config

```bash
poetry run anylogic-agent --generate-config
```

This creates `config.yaml` in the current directory if it doesn’t exist.

### Run the Agent

Default (expects `config.yaml` in current directory):

```bash
poetry run anylogic-agent
```

With a custom config file:

```bash
poetry run anylogic-agent --config-file path/to/config.yaml
```

## Distribute as a PIP Package

Build the package from `agents/anylogic`:

```bash
poetry build
```

Artifacts will be created in `dist/` (wheel and sdist).

### Verify the Package

```bash
pip install dist/anylogic_agent-<version>-py3-none-any.whl
anylogic-agent --help
```

### Release a New Version

Update `version` in `pyproject.toml`, then rebuild:

```toml
version = "0.2.0"
```

```bash
poetry build
```

## Quick Start: Client Interaction

Client resources are under `anylogic_agent/resources/`:

- `use.yaml.template` — RabbitMQ client configuration
- `use_anylogic_agent.py` — Example client (listens for results)
- `api/simulation.yaml.template` — Example simulation request payload schema

Example: copy `use.yaml.template` to `use.yaml` and run the client to listen for results routed to your agent queue:

```bash
cd agents/anylogic/anylogic_agent/resources
python use_anylogic_agent.py --config use.yaml
```

To publish a request, you can use the `send_request()` method in `use_anylogic_agent.py` or any AMQP publisher to send a YAML payload to the `ex.bridge.output` exchange with routing key `<client_id>.anylogic`.

## Workflow

1. The agent connects to RabbitMQ and declares infrastructure (exchanges, queues, bindings).
2. The agent starts a UDP listener using `udp.host:udp.port` and waits for JSON messages from the AnyLogic model.
3. Upon receiving data, it creates a response using the configured templates and publishes results to `ex.sim.result`.

## Package Development

```bash
pytest
pylint anylogic_agent
autopep8 --in-place --aggressive --recursive 'anylogic_agent'
```

## Author

<div style="display: flex; flex-direction: column; gap: 25px;"> <!-- Marco Melloni --> <div style="display: flex; align-items: center; gap: 15px;"> <img src="anylogic_agent/images/melloni.jpg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/> <div> <h3 style="margin: 0;">Marco Melloni</h3> <p style="margin: 4px 0;">Digital Automation Engineering Student<br> University of Modena and Reggio Emilia, Department of Sciences and Methods for Engineering (DISMI)</p> <div> <a href="https://www.linkedin.com/in/marco-melloni/"> <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/> </a> <a href="https://github.com/marcomelloni" style="margin-left: 8px;"> <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/> </a> </div> </div> </div> <!-- Marco Picone --> <div style="display: flex; align-items: center; gap: 15px;"> <img src="anylogic_agent/images/picone.jpeg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/> <div> <h3 style="margin: 0;">Prof. Marco Picone</h3> <p style="margin: 4px 0;">Associate Professor<br> University of Modena and Reggio Emilia, Department of Sciences and Methods for Engineering (DISMI)</p> <div> <a href="https://www.linkedin.com/in/marco-picone-8a6a4612/"> <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/> </a> <a href="https://github.com/piconem" style="margin-left: 8px;"> <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/> </a> </div> </div> </div> <!-- Prasad Talasila --> <div style="display: flex; align-items: center; gap: 15px;"> <!-- Placeholder image --> <img src="anylogic_agent/images/talasila.jpeg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/> <div> <h3 style="margin: 0;">Dr. Prasad Talasila</h3> <p style="margin: 4px 0;">Postdoctoral Researcher<br> Aarhus University</p> <div> <a href="https://www.linkedin.com/in/prasad-talasila/"> <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/> </a> <a href="https://github.com/prasadtalasila" style="margin-left: 8px;"> <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/> </a> </div> </div> </div> </div>
