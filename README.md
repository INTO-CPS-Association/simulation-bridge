# Simulation Bridge

**Simulation Bridge** is an open-source middleware designed to run **distributed simulations** involving Digital Twins (DTs), Mock Physical Twins (MockPTs), and their corresponding simulators.

With a focus on **modularity**, **reusability**, and **bidirectional communication**, Simulation Bridge acts as a universal connector across simulation environments. It enables flexible integration, real-time control, and streamlined data exchange, without being tied to a specific protocol or vendor ecosystem.

![Project](images/project.png)

## Key Capabilities

### Protocol Flexibility

Simulation Bridge supports multiple communication protocols via a modular plugin architecture, allowing easy integration and extension with custom protocol adapters. The supported protocols include:

- **RabbitMQ** (default, chosen for its robust security features)
- **MQTT**
- **REST API**
- Custom protocol plugins for tailored integrations

### Multi-Mode Interactions

Supports two simulation interaction modes:
| **Mode** | **Description** |
|---------------|----------------------------------------------------------------------|
| **Batch** | Executes the simulation without real-time feedback; results are available only at the end of the run. |
| **Streaming** | Enables continuous, real-time monitoring during simulation execution. |

### Dynamic Discoverability

Utilizes an agent-based mechanism to dynamically detect and interact with the simulator's capabilities (e.g., simulation lifecycle commands, access to simulation objects). This allows the bridge to adapt without requiring static configurations.

### Data Transformation

Automatically converts between commonly used formats such as **JSON**, **XML**, and **CSV** to meet the input/output requirements of different simulators.

## Out of Scope

To maintain performance and simplicity, Simulation Bridge explicitly does **not**:

- Handle persistent **data storage**
- Support **file-based communication** or **file system interactions**

## System Architecture Overview

![Simulation Bridge Architecture](images/software_architecture.png)

## Requirements

#### 1. Clone the Repository and Navigate to the Working Directory

```bash
git clone https://github.com/INTO-CPS-Association/simulation-bridge.git
cd simulation-bridge
```

### 2. Install Poetry and Create Virtual Environment

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

### Configuration

The configuration is specified in yaml format. A template file (`simulation_bridge/config/config.yaml.template`) has been provided. It can be customized further.

Explanation on different fields of the yaml template is given below.

```yaml
# Configuration for Simulation Bridge
simulation_bridge:
  simulation_bridge_id: simulation_bridge # Unique identifier for this Simulation Bridge instance

# RabbitMQ Connection Settings
rabbitmq:
  host: localhost # RabbitMQ server hostname or IP address
  port: 5672 # RabbitMQ server port (default: 5672)
  virtual_host: / # RabbitMQ virtual host for logical separation
  username: null # Username for authentication; null if not needed
  password: null # Password for authentication; null if not needed
  prefetch_count: 1 # Number of messages to prefetch (concurrency control)
  heartbeat: 600 # Heartbeat interval in seconds to maintain connection
  connection_attempts: 3 # Number of retry attempts for connection
  retry_delay: 5 # Delay (seconds) between connection retry attempts
  ssl:
    enabled: false # Enable SSL/TLS communication if true
    verify_hostname: true # Verify server hostname when using SSL
    ca_certs: null # Path to CA certificate file for SSL verification
    cert_file: null # Path to client certificate file (for SSL)
    key_file: null # Path to client private key file (for SSL)

# Logging Configuration
logging:
  level: DEBUG # Logging verbosity level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  file: logs/sim_bridge.log # Path to the log file

# RabbitMQ Infrastructure Configuration
infrastructure:
  exchanges: # List of RabbitMQ exchanges used by the bridge
    - name: ex.input.bridge # Exchange for input messages to the bridge
      type: topic # Exchange type (topic for pattern routing)
      durable: true # Exchange survives RabbitMQ server restarts
      auto_delete: false # Exchange is not auto-deleted when unused
      internal: false # Exchange can be published to by clients

    - name: ex.bridge.output # Exchange for output messages from the bridge
      type: topic
      durable: true
      auto_delete: false
      internal: false

    - name: ex.sim.result # Exchange for simulation results
      type: topic
      durable: true
      auto_delete: false
      internal: false

    - name: ex.bridge.result # Exchange for bridged results to other components
      type: topic
      durable: true
      auto_delete: false
      internal: false

  queues: # List of queues receiving messages from exchanges
    - name: Q.bridge.input # Queue for input messages to the bridge
      durable: true # Queue survives RabbitMQ restarts
      exclusive: false # Queue is not exclusive to a single connection
      auto_delete: false # Queue is not deleted when no longer used

    - name: Q.bridge.result # Queue for messages with simulation results
      durable: true
      exclusive: false
      auto_delete: false

    - name: Q.dt.result # Queue for Digital Twin result messages
      durable: true
      exclusive: false
      auto_delete: false

    - name: Q.pt.result # Queue for Physical Twin result messages
      durable: true
      exclusive: false
      auto_delete: false

  bindings: # Bindings linking queues to exchanges with routing keys
    - queue: Q.bridge.input # Queue to bind
      exchange: ex.input.bridge # Exchange to bind to
      routing_key: "#" # Routing key pattern: matches all messages

    - queue: Q.bridge.result # Queue to bind
      exchange: ex.sim.result # Exchange to bind to
      routing_key: "#" # Matches all messages

    - queue: Q.dt.result # Queue to bind
      exchange: ex.bridge.result # Exchange to bind to
      routing_key: "*.result" # Matches routing keys ending with ".result"

    - queue: Q.pt.result # Queue to bind
      exchange: ex.bridge.result
      routing_key: "*.result"
```

## Usage

The Simulation Bridge requires a configuration file to run. You can start by copying the provided template and customizing it as needed.

### Generating the Default Configuration File

To create a copy of the default configuration file (`config.yaml`), run the following command from the project root:

```bash
poetry run simulation-bridge --generate-config
```

This will create a copy of `simulation_bridge/config/config.yaml.template`, which you can modify according to your environment.

### Running with the Default Configuration

Once the configuration file is in place, start the Simulation Bridge with:

```bash
poetry run simulation-bridge
```

By default, the application looks for the configuration file at `simulation_bridge/config/config.yaml.template`.

### Running with a Custom Configuration File

If you want to use a custom `config.yaml` file, run the `simulation-bridge` command with the `--config-file` or `-c` option followed by the path to your configuration file:

```bash
poetry run simulation-bridge --config-file <path_to_config.yaml>
```

Alternatively, you can use the shorthand `-c` option:

```bash
poetry run simulation-bridge -c <path_to_config.yaml>
```

## Documentation

- ### Matlab

  - [**Matlab Agent** ↗](agents/matlab/README.md): Explanation of the MATLAB agent functionality and configuration.
  - [**Matlab Simulation Constraints** ↗](agents/matlab/matlab_agent/docs/README.md): A breakdown of the constraints and requirements for MATLAB-driven simulations.

## License

This project is licensed under the **INTO-CPS Association Public License v1.0**.  
See the [LICENSE](./LICENSE) file for full license text.

## Author

<div style="display: flex; flex-direction: column; gap: 25px;"> <!-- Marco Melloni --> <div style="display: flex; align-items: center; gap: 15px;"> <img src="matlab_agent/images/melloni.jpg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/> <div> <h3 style="margin: 0;">Marco Melloni</h3> <p style="margin: 4px 0;">Digital Automation Engineering Student<br> University of Modena and Reggio Emilia, Department of Sciences and Methods for Engineering (DISMI)</p> <div> <a href="https://www.linkedin.com/in/marco-melloni/"> <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/> </a> <a href="https://github.com/marcomelloni" style="margin-left: 8px;"> <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/> </a> </div> </div> </div> <!-- Marco Picone --> <div style="display: flex; align-items: center; gap: 15px;"> <img src="matlab_agent/images/picone.jpeg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/> <div> <h3 style="margin: 0;">Prof. Marco Picone</h3> <p style="margin: 4px 0;">Associate Professor<br> University of Modena and Reggio Emilia, Department of Sciences and Methods for Engineering (DISMI)</p> <div> <a href="https://www.linkedin.com/in/marco-picone-8a6a4612/"> <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/> </a> <a href="https://github.com/piconem" style="margin-left: 8px;"> <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/> </a> </div> </div> </div> <!-- Prasad Talasila --> <div style="display: flex; align-items: center; gap: 15px;"> <!-- Placeholder image --> <img src="matlab_agent/images/talasila.jpeg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/> <div> <h3 style="margin: 0;">Dr. Prasad Talasila</h3> <p style="margin: 4px 0;">Postdoctoral Researcher<br> Aarhus University</p> <div> <a href="https://www.linkedin.com/in/prasad-talasila/"> <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/> </a> <a href="https://github.com/prasadtalasila" style="margin-left: 8px;"> <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/> </a> </div> </div> </div> </div>
