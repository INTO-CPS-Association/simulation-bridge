# Setup Instructions

Adhere to the following steps to configure and execute the **Simulation Bridge** effectively.

## Install Requirements

### 1. Install Poetry

Ensure that Poetry is installed on your system. If it is not already installed, execute the following command:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install poetry
```

Verify the installation by checking the Poetry version:

```bash
poetry --version
```

### 2. Clone the Repository

Clone the Simulation Bridge repository to your local environment:

```bash
git clone https://github.com/INTO-CPS-Association/simulation-bridge
cd simulation-bridge
```

### 3. Install Dependencies

Use Poetry to install the project dependencies specified in the `pyproject.toml` file:

```bash
poetry install
```

This will install all required libraries for the project.

---

## Install RabbitMQ

The Simulation Bridge requires an active RabbitMQ server. You can choose one of the following options:

### Option 1: Install RabbitMQ Locally

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

### Option 2: Use a Remote RabbitMQ Server

Alternatively, connect to an existing RabbitMQ instance hosted on a remote server (on-premise or cloud).

---

## Agents

### Matlab Agent

#### 1. MATLAB Engine API for Python

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

#### 2. Configuration

For detailed instructions on configuring the MATLAB agent, refer to the [MATLAB Agent Configuration Guide](agents/matlab/README.md). Ensure that all necessary settings are correctly applied to enable seamless integration.

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
