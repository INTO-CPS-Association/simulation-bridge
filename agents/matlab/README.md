# MATLAB agent

The MATLAB Agent is a Python-based connector designed to interface with MATLAB simulations through various methods. It provides the following functionalities:

- **Batch Simulation**: Executes predefined MATLAB routines with specified input parameters, collecting the final results upon completion.
- **Streaming Simulation (Agent-Based)**: Allows sending input once, with the output being received in real-time during the simulation.

The MATLAB Agent is primarily built to integrate with the Simulation Bridge but can also be utilized by external systems via RabbitMQ exchange methods. Communication parameters and other settings are defined in the configuration file located at `matlab_agent/config/config.yaml`.

<div align="center">
  <img src="matlab_agent/images/structure.png" alt="MATLAB Agent Structure" width="600" style="border: 1px solid #ddd; border-radius: 4px; padding: 5px;">
</div>

## Instruction

To integrate MATLAB with the Simulation Bridge, install the MATLAB Engine API for Python. Follow the official MathWorks installation guide for detailed steps:

[MATLAB Engine API for Python Installation Guide](https://www.mathworks.com/help/matlab/matlab-engine-for-python.html)

> **Installation on macOS**
>
> For macOS users (e.g., MATLAB R2024b), execute the following commands:
>
> ```bash
> poetry shell
> cd /Applications/MATLAB_R2024b.app/extern/engines/python
> python -m pip install .
> ```
>
> **Note:** Replace `MATLAB_R2024b.app` with the version installed on your system.

Verify that the MATLAB Engine is properly installed and accessible within your Python environment.

## Usage

### Running the Agent

To launch the MATLAB Agent using the default configuration (`agent_id=matlab`), follow these steps:

1. Open a terminal and navigate to the root directory of the project.
2. Execute the following command:

```bash
poetry run matlab-agent
```

If you want to specify a custom `agent_id`, add your desired identifier in the command:

```bash
poetry run matlab-agent <custom_agent_id>
```

For example, to use `agent_id_custom` as the identifier, run:

```bash
poetry run matlab-agent agent_id_custom
```

To modify the default `agent_id` setting, update the configuration file before launching the agent.

### Configuration

The agent's behavior is controlled through the configuration file. Key options include:

- **Agent Settings**: Define the agent's ID and other operational parameters.
- **RabbitMQ Settings**: Configure server connection details like `host`, `port`, `username`, and `password`.
- **Exchange and Queue Settings**: Specify input/output exchanges, queue durability, and message prefetch limits.
- **Logging**: Adjust logging levels and file paths.
- **TCP Settings**: Set up host and port for TCP connections.
- **Response Templates**: Customize formats for success, error, and progress responses.

Refer to the configuration file for detailed descriptions of each parameter.

## Workflow

1. The agent connects to RabbitMQ and sets up the required queues and exchanges.
2. It listens for incoming messages on its dedicated queue.
3. Upon receiving a message:

- It analyzes and processes the simulation request.
- Executes the simulation.
- Sends the results to the output exchange.

For detailed information regarding simulations and constraints, please refer to the [Simulations and Constraints Documentation](matlab_agent/docs/README.md).

## Author

<div align="left" style="display: flex; align-items: center; gap: 15px;">
  <img src="matlab_agent/images/profile.jpg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/>
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
