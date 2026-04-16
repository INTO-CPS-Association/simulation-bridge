# Simulation Bridge Design

## Purpose

`simulation_bridge` is an event-driven middleware that receives simulation requests over external protocols, normalizes and routes them to simulator agents via RabbitMQ, and forwards simulator results back to the originating protocol/client.

The package also provides an in-process mode (`SimulationBridge` in the in-memory adapter) for Python-only usage without network-facing adapters.

## Architectural Style

- **Core style**: protocol-adapter + event bus + brokered backend.
- **External interfaces**: REST (Quart/Hypercorn), MQTT (paho-mqtt), RabbitMQ (pika), and in-memory callbacks (Blinker).
- **Internal coordination**: Blinker signals managed by `SignalManager`.
- **Simulation transport backbone**: RabbitMQ exchanges/queues are the common transport for input (`ex.bridge.output`) and results (`ex.bridge.result` / `ex.sim.result`).

## Main Runtime Components

### 1. Entry point and lifecycle

- `simulation_bridge/src/main.py`
  - CLI flags: `--generate-config`, `--generate-project`, `--config-file`.
  - Starts `BridgeOrchestrator`.

### 2. Orchestration layer

- `BridgeOrchestrator` (`src/core/bridge_orchestrator.py`)
  - Loads validated config (`ConfigManager`).
  - Ensures certificates for REST TLS (`ensure_certificates`).
  - Sets up RabbitMQ infrastructure (exchanges/queues/bindings).
  - Dynamically imports adapter classes from protocol config JSON.
  - Instantiates enabled adapters, registers signal callbacks, starts/stops adapters, and monitors liveness.

### 3. Bridge core

- `BridgeCore` (`src/core/bridge_core.py`)
  - Validates inbound payloads with Pydantic models.
  - Injects protocol metadata into `simulation.bridge_meta`.
  - Publishes normalized requests to RabbitMQ (`ex.bridge.output`).
  - Routes simulator results from RabbitMQ back to bridge output/result exchanges.
  - Handles RabbitMQ reconnect-and-retry behavior for publish failures.

### 4. Protocol adapters

- **RabbitMQAdapter**: consumes bridge input/result queues; emits Blinker signals.
- **MQTTAdapter**: subscribes input topic, emits input signals, publishes result topic.
- **RESTAdapter**:
  - Validates Bearer JWT (HS256 policy checks + required claims).
  - Accepts YAML/JSON bodies and returns NDJSON streaming responses.
  - Uses per-producer async queues for live result streaming.
- **InMemoryAdapter**:
  - Sends requests via signal and routes async results to request callbacks.
  - Buffers pending results until callback registration.

### 5. Utility subsystems

- `ConfigManager` + `config_loader`:
  - YAML loading, environment substitution, and Pydantic validation.
- `SignalManager`:
  - Connect/disconnect of protocol signal map defined in JSON descriptors.
- `PerformanceMonitor`:
  - Singleton metrics recorder keyed by `(operation_id, protocol, client_id, simulation_type)`.
  - Captures timing, CPU/RSS, overhead columns, and writes CSV.
- `certs.py`:
  - Self-signed certificate generation/validation for REST TLS files.

## Request/Result Flow

1. Protocol adapter receives client request.
2. Adapter records initial metrics and emits an input signal.
3. `BridgeCore.handle_input_message` validates and republishes to RabbitMQ for simulator agents.
4. Simulator agent processes and publishes result to `ex.sim.result`.
5. `RabbitMQAdapter` consumes result queue and dispatches by originating protocol in `bridge_meta`.
6. Target adapter delivers response:
   - REST: NDJSON stream frame.
   - MQTT: publish to output topic.
   - RabbitMQ: publish result route.
   - In-memory: callback invocation.
7. Performance monitor finalizes operation on terminal status (`completed`).

## Configuration-Driven Design

- Bridge behavior is mostly configuration-driven:
  - Transport/endpoints in YAML (`config.yaml`).
  - Adapter-to-signal bindings in protocol JSON files under `src/protocol_adapters/`.
  - Logging/performance output locations in config.
- Environment substitution supports `${VAR}` and `${VAR:default}` placeholders.

## Security and Reliability Design

- **REST auth**: strict JWT validation path (rejects malformed, `alg=none`, unsupported headers, JWE/nested JWT, and stale tokens).
- **TLS**:
  - RabbitMQ TLS optional.
  - REST HTTPS cert/key auto-generated if missing or invalid.
- **Broker robustness**:
  - RabbitMQ reconnect attempts in core/infrastructure/adapter layers.
  - Explicit message ack/nack behavior in queue consumers.

## Extensibility Model

To add a new protocol:

1. Implement a `ProtocolAdapter` subclass.
2. Add protocol entry with adapter class path + signal mappings in protocol JSON.
3. Add adapter config section to YAML + config model.
4. Add tests for routing, startup/shutdown, and signal behavior.

This preserves the existing contract: adapters translate protocol semantics, while `BridgeCore` keeps routing/business logic centralized.
