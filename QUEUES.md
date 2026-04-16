# Messaging Infrastructure — Exchanges, Queues & Bindings

This document maps every RabbitMQ exchange, queue, and binding used by the
Simulation Bridge and its agents.  MQTT and REST endpoints are included for
completeness.

---

## Overview

```
Digital Twin (DT)
  │
  │  publishes to ex.input.bridge          ┌──────────────────────┐
  ├──────────────────────────────────────▸  │  Simulation Bridge   │
  │  (also: MQTT bridge/input,              │                      │
  │   REST POST /message)                   │  Q.bridge.input  ◂── ex.input.bridge (#)
  │                                         │  Q.bridge.result ◂── ex.sim.result  (#)
  │                                         │                      │
  │  consumes Q.{dt_id}.result              │  publishes to        │
  ◂─────────────────────────────────────────│  ex.bridge.output    │
     (bound to ex.bridge.result *.result)   │  ex.bridge.result    │
                                            └──────┬───────────────┘
                                                   │
                     publishes to ex.bridge.output  │
                     (routing_key: {dt_id}.{agent}) │
                                                   ▾
                              ┌─────────────────────────────────┐
                              │        Simulation Agents        │
                              │                                 │
                              │  Q.sim.matlab  ◂── ex.bridge.output (*.matlab)
                              │  Q.sim.simul8  ◂── ex.bridge.output (*.simul8)
                              │                                 │
                              │  publishes to ex.sim.result     │
                              │  (routing_key: {agent}.result.{dt_id})
                              └─────────────────────────────────┘
```

---

## Exchanges

| Exchange | Type | Durable | Owner | Purpose |
|---|---|---|---|---|
| `ex.input.bridge` | topic | yes | Bridge | Receives simulation requests from DTs |
| `ex.bridge.output` | topic | yes | Bridge | Forwards requests to simulation agents |
| `ex.sim.result` | topic | yes | Agents | Receives simulation results from agents |
| `ex.bridge.result` | topic | yes | Bridge | Delivers results back to DTs |
| `ex.input.stream` | topic | yes | MATLAB agent | Streams real-time data for interactive simulations |

**Defined in:**

- Bridge exchanges: [`simulation_bridge/config/config.yaml.template`](simulation_bridge/config/config.yaml.template) → `rabbitmq.infrastructure.exchanges`
- Agent exchanges: [`agents/matlab/matlab_agent/config/config.yaml.template`](agents/matlab/matlab_agent/config/config.yaml.template) and [`agents/simul8/simul8_agent/config/config.yaml.template`](agents/simul8/simul8_agent/config/config.yaml.template) → `exchanges.input` / `exchanges.output`
- Stream exchange: [`agents/matlab/matlab_agent/src/utils/constants.py`](agents/matlab/matlab_agent/src/utils/constants.py) → `EXCHANGE_INPUT_STREAM`

---

## Queues

### Bridge Queues

| Queue | Durable | Bound To | Routing Key | Purpose |
|---|---|---|---|---|
| `Q.bridge.input` | yes | `ex.input.bridge` | `#` (all) | All incoming DT requests |
| `Q.bridge.result` | yes | `ex.sim.result` | `#` (all) | All agent results |

**Defined in:** `simulation_bridge/config/config.yaml.template` → `rabbitmq.infrastructure.queues` / `bindings`

### Agent Queues

| Queue | Durable | Bound To | Routing Key | Purpose |
|---|---|---|---|---|
| `Q.sim.matlab` | yes | `ex.bridge.output` | `*.matlab` | MATLAB agent input |
| `Q.sim.simul8` | yes | `ex.bridge.output` | `*.simul8` | Simul8 agent input |
| `Q.{agent_id}.interactive.{request_id}` | yes | `ex.input.stream` | user-defined | Interactive-mode streaming (MATLAB only) |

**Defined in:**

- Queue name: `agents/matlab/matlab_agent/src/comm/rabbitmq/rabbitmq_manager.py` → `f'Q.sim.{self.agent_id}'`
- Binding: same file, `queue_bind(routing_key=f'*.{self.agent_id}')`
- Interactive queue: `agents/matlab/matlab_agent/src/core/interactive.py`

### Digital-Twin Client Queues

| Queue | Durable | Bound To | Routing Key | Purpose |
|---|---|---|---|---|
| `Q.{dt_id}.result` | yes | `ex.bridge.result` | `*.result` | DT receives its results |

**Defined in:** `simulation_bridge/resources/rabbitmq/rabbitmq_use.yaml.template` → `queue.result_queue_prefix` / `routing_key`

---

## Message Flow

### 1. Request Path (DT → Agent)

```
DT publishes to ex.input.bridge
    routing_key: {dt_id}

        ↓ bound with #

Q.bridge.input → RabbitMQAdapter._handle_input_queue()
    → signal: message_received_input_rabbitmq
    → BridgeCore.handle_input_message()
        • Registers routing entry (pa_n, request_id, client_id, timeout)
        • Generates bridge_index (anti-spoofing token)
        • Deduplicates by (request_id, client_id, simulator)
        • Clamps timeout to [min_timeout, max_timeout]

Bridge publishes to ex.bridge.output
    routing_key: {dt_id}.{simulator}

        ↓ bound with *.{agent_id}

Q.sim.{agent_id} → Agent.message_handler()
    → Dispatches to batch / streaming / interactive handler
```

### 2. Result Path (Agent → DT)

```
Agent publishes to ex.sim.result
    routing_key: {agent_id}.result.{dt_id}

        ↓ bound with #

Q.bridge.result → RabbitMQAdapter._handle_result_queue()
    → Extracts bridge_meta.protocol to determine north-bound PA
    → signal: message_received_result_{protocol}
       or: message_received_result_unknown (if protocol missing)
    → BridgeCore.handle_result_message()
        • Looks up routing entry by request_id
        • Validates bridge_index
        • Overwrites destinations with routing-table DT
        • Routes to correct north-bound PA
        • Removes entry on terminal status (completed/failed/error)

Bridge publishes to ex.bridge.result  (if PA_N = rabbitmq)
    routing_key: {source}.result

        ↓ bound with *.result

Q.{dt_id}.result → DT consumes result
```

### 3. Interactive Streaming (MATLAB only)

```
External data source publishes to ex.input.stream
    routing_key: user-defined (from simulation request stream_source)

        ↓

Q.{agent_id}.interactive.{request_id}
    → MATLAB agent polls with basic_get()
    → Forwards data to MATLAB process via TCP
    → MATLAB sends results back via TCP
    → Agent publishes to ex.sim.result (normal result path)
```

---

## MQTT Topics

| Topic | Direction | Purpose |
|---|---|---|
| `bridge/input` | DT → Bridge | Simulation requests via MQTT |
| `bridge/output` | Bridge → DT | Simulation results via MQTT |

**Defined in:** `simulation_bridge/config/config.yaml.template` → `mqtt.input_topic` / `output_topic`

---

## REST Endpoints

| Endpoint | Method | Direction | Purpose |
|---|---|---|---|
| `POST /message` | POST | DT → Bridge | Submit simulation request (JWT-authenticated) |
| SSE stream | GET | Bridge → DT | Receive results (Server-Sent Events) |

**Defined in:** `simulation_bridge/config/config.yaml.template` → `rest.endpoint`

---

## Signal Routing (Internal)

The bridge uses [blinker](https://pypi.org/project/blinker/) signals to
decouple protocol adapters from core logic.

| Signal | Source | Handler | File |
|---|---|---|---|
| `message_received_input_rabbitmq` | RabbitMQ adapter | `BridgeCore.handle_input_message` | `adapters_signal.json` |
| `message_received_result_rabbitmq` | RabbitMQ adapter | `BridgeCore.handle_result_message` | `adapters_signal.json` |
| `message_received_result_mqtt` | MQTT adapter | `BridgeCore.handle_result_message` | `adapters_signal.json` |
| `message_received_result_rest` | REST adapter | `BridgeCore.handle_result_message` | `adapters_signal.json` |
| `message_received_result_unknown` | RabbitMQ adapter | `BridgeCore.handle_result_unknown_message` | `adapters_signal.json` |
| `message_received_result_inmemory` | InMemory adapter | `BridgeCore.handle_result_message` | `inmemory_signal.json` |
| `message_received_input_inmemory` | InMemory adapter | `BridgeCore.handle_input_message` | `inmemory_signal.json` |

**Defined in:**

- [`simulation_bridge/src/protocol_adapters/adapters_signal.json`](simulation_bridge/src/protocol_adapters/adapters_signal.json)
- [`simulation_bridge/src/protocol_adapters/inmemory_signal.json`](simulation_bridge/src/protocol_adapters/inmemory_signal.json)

---

## QoS & Prefetch

| Component | Prefetch Count | Notes |
|---|---|---|
| Simulation agents | 1 | Process one message at a time |
| Bridge | unlimited (default) | No explicit prefetch limit |

---

## Message Persistence

All queues are **durable** and all messages use **delivery_mode=2**
(persistent).  Messages survive broker restarts.  The bridge NACKs (without
requeue) messages it cannot process, sending them to the dead-letter exchange
if one is configured.
