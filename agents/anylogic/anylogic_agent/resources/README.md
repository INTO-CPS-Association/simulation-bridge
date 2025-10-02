# AnyLogic Agent Client

This directory contains a Python client for interacting with an AnyLogic Agent via RabbitMQ. The provided tools enable you to send simulation requests and receive results efficiently, using straightforward YAML configuration files.

## Overview

- **Streaming Client (`use_anylogic_agent_streaming.py`)**  
   Publishes simulation requests and listens asynchronously for results until the simulation completes.

## Getting Started

1. **Configuration**  
   Create a YAML configuration file (default: `use.yaml`) specifying RabbitMQ connection parameters and the path to the simulation request payload.

2. **Running the Client**  
   Execute the streaming client to submit a request and receive results:

   ```bash
   python use_anylogic_agent_streaming.py --config use.yaml --payload request.yaml
   ```

   By default, if command-line options are not provided, the client searches for these files in the current directory.

## Streaming Client Details

- **Purpose:**  
   Sends simulation requests to the AnyLogic Agent and waits for results.

- **Workflow:**

  1.  Parses command-line arguments for configuration and payload files.
  2.  Loads RabbitMQ credentials and simulation payload from YAML files.
  3.  Publishes the payload to the agent via RabbitMQ.
  4.  Listens on a dedicated result queue for messages.
  5.  Prints each result; exits when a message with `status: completed` is received.

- **Command-line Options:**
  - `--config PATH` : Specify an alternative YAML configuration file (default: `use.yaml`).
  - `--payload PATH` : Specify a custom payload file path.

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

Simulation results are received on a queue named `Q.<agent_id>.anylogic.result`, which is bound to the `ex.sim.result` exchange.
