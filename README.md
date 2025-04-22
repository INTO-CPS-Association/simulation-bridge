# Simulation Bridge

The **Simulation Bridge** is an open-source middleware solution designed to enable seamless and dynamic communication between Digital Twins (DT), Mock Physical Twins (MockPT), and their dedicated Simulator counterparts. It serves as a **modular**, **reusable**, and **bidirectional** bridge, supporting multiple protocols and interaction modes to ensure interoperability across diverse simulation environments.

Built around the concept of simulation, the bridge facilitates control, monitoring, and data exchange among the involved entities, providing a universal middleware solution that enhances flexibility and integration within simulation-based systems.

![Project](images/project.png)

## Overview

![Simulation Bridge Architecture](images/software_architecture.png)

---

## Key Features

### 🌐 Multi-Protocol Support

- **RabbitMQ** (default)
- **MQTT**
- **REST API**
- Custom protocol plugins for tailored integrations

### ⚙️ Flexible Interaction Modes

| **Mode**        | **Description**                                       |
| --------------- | ----------------------------------------------------- |
| **Batch**       | Execute simulations without real-time monitoring.     |
| **Interactive** | Enable real-time monitoring and control.              |
| **Hybrid**      | Combine batch execution with interactive adjustments. |

### 🔍 Intelligent Discoverability

- Dynamic capability detection through an advanced agent system.
- Automatic registration of simulator features for seamless integration.

### 🔄 Advanced Data Transformation

- Effortless conversion between **JSON**, **XML**, and **CSV** formats.
- Protocol-agnostic data formatting to ensure compatibility across systems.

---

## Documentation

Get started with the Simulation Bridge and unlock its full potential using these essential resources:

- [📘 **Instruction Guide** ↗](INSTRUCTION.md): A comprehensive guide to set up, configure, and deploy the Simulation Bridge.
- [🚀 **Usage Guide** ↗](USAGE.md): Detailed instructions on how to run the Simulation Bridge and its components.
- [🔗 **MATLAB Agent Documentation** ↗](agents/MATLABagent/README.md): In-depth explanation of the MATLAB agent functionality and configuration.
- [⚙️ **MATLAB Simulation Constraints** ↗](tests/simulations/matlab/README.md): A breakdown of the constraints and requirements for MATLAB-driven simulations.

These resources are crafted to empower you with the technical expertise and practical insights needed to fully leverage the Simulation Bridge in your projects.

---

## License

This project is licensed under the **INTO-CPS Association Public License v1.0**.  
See the [LICENSE](./LICENSE) file for full license text.

---

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
