# RabbitMQ Messaging System

## System Architecture

### Main Components

- **Data Sources (DT, PT, MockPT)**  
   These components generate data and publish it to the `ex.input.bridge` exchange.  
   Routing key format: `<source>` (e.g., `dt`, `pt`).

- **Simulation Bridge**  
   Acts as an intermediary, receiving messages from the `Q.bridge.input` queue.  
   Processes and routes messages to the `ex.bridge.output` exchange.  
   Routing key format: `<source>.<destination>`.

- **Simulations**  
   Specialized consumers that listen to specific queues.  
   Binding pattern: `*.simX` to capture messages intended for `simX`.

## RabbitMQ Topology

| **Exchange**       | **Type** | **Description**                    |
| ------------------ | -------- | ---------------------------------- |
| `ex.input.bridge`  | `topic`  | Entry point for all incoming data. |
| `ex.bridge.output` | `topic`  | Exit point for advanced routing.   |

| **Queue**        | **Binding Key** | **Description**                   |
| ---------------- | --------------- | --------------------------------- |
| `Q.bridge.input` | `#`             | Receives all input messages.      |
| `Q.sim.<ID>`     | `*.<ID>`        | Dedicated queues for simulations. |

## Routing Key Specification

### Format

`<source>.<destination>`

- **Source**: Unique identifier of the producer.  
   Examples: `dt`, `pt`, `mockpt`.

- **Destination**: Identifier of the recipient.
  - Format: `sim<ID>` for specific simulations.
  - Use `broadcast` for general messages.

### Examples

| **Scenario**          | **Routing Key** | **Description**           |
| --------------------- | --------------- | ------------------------- |
| DT → Simulation A     | `dt.simA`       | Direct message.           |
| PT → Broadcast        | `pt.broadcast`  | Message to all consumers. |
| MockPT → Simulation B | `mockpt.simB`   | Message from mock source. |

## Data Flow

### Message Publishing

Producers publish to `ex.input.bridge` with:

- A base routing key (`source`).
- A payload containing a `destinations` field.

### Bridge Processing

- Messages are received from `Q.bridge.input`.
- For each destination in the payload:
  - The full routing key is constructed.
  - The message is re-published to `ex.bridge.output`.

### Message Consumption

Simulations consume messages:

- With routing keys ending in their ID.
- From any authorized source.

## Flow Diagram

```mermaid
flowchart TD
     %% Custom Styles
     classDef producer fill:#E3F2FD,stroke:#42A5F5,stroke-width:2px;
     classDef bridge fill:#FFF3E0,stroke:#FFA726,stroke-width:2px;
     classDef consumer fill:#E8F5E9,stroke:#66BB6A,stroke-width:2px;
     classDef exchange fill:#F3E5F5,stroke:#AB47BC,stroke-width:2px;
     classDef queue fill:#FCE4EC,stroke:#EC407A,stroke-width:2px;

     %% Producers Subgraph
     subgraph Producers
          direction TB
          DT["DT (Digital Twin)"]:::producer
          PT["PT (Physical Twin)"]:::producer
          MockPT["MockPT (Mock Twin)"]:::producer
     end

     %% Bridge Subgraph
     subgraph Bridge["Simulation Bridge"]
          direction TB
          EX1["ex.input.bridge (Exchange)"]:::exchange
          Q1["Q.bridge.input (Queue)"]:::queue
          Logic["Bridge Logic (Routing)"]:::bridge
          EX2["ex.bridge.output (Exchange)"]:::exchange
     end

     %% Consumers Subgraph
     subgraph SimA["SimA"]
          direction TB
          QSimA["Q.sim.simA"]:::queue
          SimAService["Simulation A"]:::consumer
     end

     subgraph SimB["SimB"]
          direction TB
          QSimB["Q.sim.simB"]:::queue
          SimBService["Simulation B"]:::consumer
     end

     %% Message Flow
     DT -->|Routing Key: dt| EX1
     PT -->|Routing Key: pt| EX1
     MockPT -->|Routing Key: mockpt| EX1

     EX1 --> Q1
     Q1 --> Logic
     Logic -->|Routing Key: dt.simA| EX2
     Logic -->|Routing Key: dt.simB| EX2

     EX2 --> QSimA --> SimAService
     EX2 --> QSimB --> SimBService
```

### Instructions for Use

1. Start RabbitMQ.
2. Launch the bridge: `python bridge.py`.
3. Start the simulations:
   ```bash
   python simulation.py simA
   python simulation.py simB
   ```
4. Send messages:
   ```bash
   python dt.py
   ```

## Author

<div align="left" style="display: flex; align-items: center; gap: 15px;">
  <img src="../../images/profile.jpg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/>
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
