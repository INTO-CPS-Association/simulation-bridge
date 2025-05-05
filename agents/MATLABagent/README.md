# Description

The MATLAB Agent is an interface that enables MATLAB simulations to be executed via RabbitMQ messages. The application receives simulation requests, processes them, and returns the results through a distributed messaging system.

## Project Structure

```
matlab_agent/
├── **init**.py
├── main.py
├── config/
│   ├── **init**.py
│   └── config.yaml
├── utils/
│   ├── **init**.py
│   └── logger.py
├── core/
│   ├── **init**.py
│   ├── agent.py
│   ├── config_manager.py
│   └── rabbitmq_manager.py
└── handlers/
    ├── **init**.py
    └── message_handler.py
```

## Components

- **main.py**: Entry point of the application.
- **core/agent.py**: Main implementation of the MATLAB agent.
- **core/config_manager.py**: Manages application configuration.
- **core/rabbitmq_manager.py**: Handles RabbitMQ connection and infrastructure.
- **handlers/message_handler.py**: Processes incoming messages.
- **utils/logger.py**: Configures the logging system.
- **config/config.yaml**: YAML configuration file.

## Usage

### Starting the Agent

To start the agent in default mode with `<id>=matlab`, navigate to the root directory and execute:

```bash
poetry run matlab-agent
```

Alternatively, run the `main.py` file in the `MATLABagent` directory, specifying an agent ID:

```bash
python main.py <agent_id>
```

For example:

```bash
python main.py matlab_agent_1
```

### Configuration

The agent's behavior can be customized by modifying the `config/config.yaml` file. Key configuration options include:

- RabbitMQ connection settings (host, port, credentials)
- Exchange names
- Queue settings
- Logging configuration

## Workflow

1. The agent connects to RabbitMQ and sets up the required queues and exchanges.
2. It listens for incoming messages on its dedicated queue.
3. Upon receiving a message:
   - It analyzes and processes the simulation request.
   - Executes the simulation (currently a placeholder).
   - Sends the results to the output exchange.

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
