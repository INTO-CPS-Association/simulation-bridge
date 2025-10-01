# ANYLOGIC Agent Clients

This directory provides Python clients for interacting with an ANYLOGIC Agent via RabbitMQ. These tools allow you to send simulation requests and receive results directly, using simple YAML configuration files.

## Overview

- **Streaming Client (`use_anylogic_agent_streaming.py`)**  
   Publishes simulation requests and listens for asynchronous results until completion.

## Getting Started

1. **Configuration**  
   Prepare a YAML config file (default: `use.yaml`) specifying RabbitMQ connection details and the simulation request payload path.

2. **Running the Client**  
   Use the streaming client to send a request and receive results:
   ```bash
   python use_anylogic_agent_streaming.py --config use.yaml --payload request.yaml
   ```

## Streaming Client Details

- **Purpose:**  
   Sends a simulation request to ANYLOGIC Agent and waits for results.

- **Workflow:**

  1.  Parses CLI arguments for config and payload files.
  2.  Loads RabbitMQ credentials and simulation payload from YAML.
  3.  Publishes the payload to the agent via RabbitMQ.
  4.  Listens on a dedicated result queue for messages.
  5.  Prints each result; exits when `status: completed` is received.

- **Command-line Options:**
  - `--config PATH` : Specify alternate YAML config file (default: `use.yaml`).
  - `--payload PATH` : Override payload path from config.

## Example use.yaml Configuration

```yaml
rabbitmq:
  host: localhost # RabbitMQ server hostname or IP address
  port: 5672 # RabbitMQ server port
  username: guest # RabbitMQ username
  password: guest # RabbitMQ password
  heartbeat: 600 # Heartbeat interval in seconds
  vhost: / # RabbitMQ virtual host

# Default path to the simulation YAML payload
# Absolute or relative path of the file in single quotes
simulation_request: simulation.yaml
```

## Result Queue

Results are received on a queue named `Q.<agent_id>.anylogic.result` bound to the `ex.sim.result` exchange.
