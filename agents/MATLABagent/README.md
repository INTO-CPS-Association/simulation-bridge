# <span style="color:orange">MATLAB</span> Agent

## Documentation

**MATLAB Agent** is a Python-based connector designed to interface with MATLAB simulations using the MATLAB Engine API. It enables control, interaction, input/output exchange, and monitoring of three types of simulations:

- Batch Simulation – send inputs and retrieve results.
- Interactive Simulation (Agent Based) – interact and visualize data in real time.
- Hybrid Simulation – mix of interactive control and output processing.

Communication with the Simulation Bridge, as well as other potential external systems, is handled by default through RabbitMQ. Configuration is driven by a **config_agent.yaml** file which sets up the message queues and RabbitMQ connectivity.

<!-- <div align="center">
  <img src="images/MATLAB-logo.png" alt="Matlab" width="50%" style="margin-bottom: 10px;"/>
</div> -->

# Architecture Overview

<div align="center">
  <img src="images/Structure.png" alt="Structure MATLAB agent" width="100%" style="margin-bottom: 10px;"/>
</div>

## Simulation Types and Flow

### General Flow

1. The **Simulation Bridge** sends input as a YAML string via **RabbitMQ** (see [Message Format](#message-format)).

2. `RabbitMQClient` receives the message and subscribes to the appropriate queues based on the parameters defined in `config_agent.yaml` (see [Configuration](#configuration)).

3. `Main` routes the message to the appropriate simulation handler. Depending on the specified simulation type, control is passed to:
   - `Batch`
   - `Interactive`
   - `Hybrid`

---

### 1. Batch Simulation

- Executes a MATLAB `.m` script (Simulation) using the **MATLAB API Engine for Python**.
- Simulation results are returned as structured Python objects.
- Results are encoded as YAML strings and published back to the Simulation Bridge via RabbitMQ.

> 📁 Example output messages can be found in the `/images/output-batch-*` folder.

<div align="center">
  <img src="images/output-batch-1.png" alt="Batch Output 1" width="30%" style="margin-right: 10px;"/>
  <img src="images/output-batch-2.png" alt="Batch Output 2" width="30%" style="margin-right: 10px;"/>
  <img src="images/output-batch-3.png" alt="Batch Output 3" width="30%"/>
</div>

---

### 2. Interactive Simulation

- The MATLAB simulation must save runtime data to a `.mat` file named `agent_data.mat`
- The `Interactive` module reads variables in real time from the `.mat` file.
- Data is streamed continuously to the Simulation Bridge via RabbitMQ.

---

### 3. Hybrid Simulation

> 🚧 **Work in Progress**

- Aims to support both:
  - Real-time interaction with the simulation.
  - Batch-style output processing.
- Designed to enable dynamic scenario adjustment during execution.

---

## Communication with Matlab

All modules use the MATLAB Engine API for Python to control MATLAB sessions.

---

## Configuration

The `config_agent.yaml` file contains the necessary settings to run the agent and establish a connection with a RabbitMQ server. It defines both the RabbitMQ connection parameters and the queue names used for message communication.

### 🔌 RabbitMQ Connection Settings

The following parameters are required to configure the RabbitMQ connection:

- **host**: Hostname or IP address of the RabbitMQ server (e.g., `localhost`).
- **port**: Port number for the RabbitMQ connection (default is `5672`).
- **virtual_host**: The virtual host to use within RabbitMQ.
- **username**: RabbitMQ username.
- **password**: RabbitMQ password.
- **heartbeat**: Interval (in seconds) to keep the connection alive.
- **blocked_connection_timeout**: Timeout value (in seconds) in case of connection blockage.
- **ssl**: Set to `true` to enable SSL/TLS connection.
- **ssl_cafile**: _(Optional)_ Path to the CA certificate file.
- **ssl_certfile**: _(Optional)_ Path to the client certificate.
- **ssl_keyfile**: _(Optional)_ Path to the client private key.

### 📬 Queue Definitions

The following queues are used for communication:

- **request**: Queue the agent listens to for incoming simulation requests.
- **response**: Queue used to publish simulation results.
- **data**: Queue used to stream real-time updates (for interactive simulations).

### 📁 Example Configuration

Below is an example of a `config_agent.yaml` file:

```yaml
rabbitmq:
  host: "localhost"
  port: 5672
  virtual_host: "/"
  username: "guest"
  password: "guest"
  heartbeat: 60
  blocked_connection_timeout: 300
  ssl: false
  ssl_cafile: "/path/to/ca.pem"
  ssl_certfile: "/path/to/client_cert.pem"
  ssl_keyfile: "/path/to/client_key.pem"

queues:
  request: "queue_simulation"
  response: "queue_response"
  data: "agent_updates"
```

> 📝 Notes
>
> - Ensure that the `config_agent.yaml` file is accessible at runtime. By default, the expected path is typically `config/config_agent.yaml` relative to the project root unless otherwise specified in the code.
> - If SSL/TLS is enabled, make sure the certificate files are correctly configured and accessible.

---

## Message Format

**Simulation Bridge → MATLAB Agent**

```python
message = yaml.dump({'simulation': simulation_data['simulation']})
```

The agent expects an input message formatted as valid YAML containing the simulation parameters.

## Author

<div align="left" style="display: flex; align-items: center; gap: 15px;">
  <img src="images/profile.jpg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/>
  <div>
    <h3 style="margin: 0;">Marco Melloni</h3>
    <div style="margin-top: 5px;">
      <a href="https://www.linkedin.com/in/marco-melloni/">
        <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/>
      </a>
      <a href="https://github.com/marcomelloni" style="margin-left: 8px;">
        <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/>
      </a>
    </div>
  </div>
</div>
