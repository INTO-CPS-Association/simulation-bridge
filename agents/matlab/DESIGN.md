# MATLAB Agent Design

## Purpose

`agents/matlab` provides a RabbitMQ-connected execution agent that receives simulation requests from the bridge, runs MATLAB simulations, and publishes structured results back to `ex.sim.result`.

Supported modes:

- `batch`
- `streaming`
- `interactive`

## Architectural Style

- **Core style**: message-driven worker with mode-specific execution controllers.
- **Transport**: RabbitMQ for control/results, TCP sockets for streaming/interactive MATLAB data channels.
- **Execution backend**:
  - MATLAB Engine API for batch mode.
  - External MATLAB process (`matlab -batch ...`) for streaming/interactive wrappers.

## Main Components

### 1. Entry point and bootstrap

- `matlab_agent/src/main.py`
  - CLI: `--generate-config`, `--generate-project`, `--config-file`.
  - Initializes logger + `MatlabAgent`.

### 2. Agent shell

- `MatlabAgent` (`src/core/agent.py`)
  - Loads validated config via `ConfigManager`.
  - Initializes singleton `PerformanceMonitor`.
  - Creates `Connect` abstraction and wires broker + message handler.
  - Starts consuming simulation requests.

### 3. Communication layer

- `Connect` (`src/comm/connect.py`)
  - Broker abstraction currently backed by `RabbitMQManager`.
- `RabbitMQManager` (`src/comm/rabbitmq/rabbitmq_manager.py`)
  - Connect/retry, exchange+queue setup, consume loop, result publish.
  - Input queue format: `Q.sim.<agent_id>`.
  - Input binding: `*.{agent_id}` on `ex.bridge.output`.
- `MessageHandler` (`src/comm/rabbitmq/message_handler.py`)
  - YAML payload parsing and Pydantic validation.
  - Dispatch by `simulation.type` to batch/streaming/interactive handlers.
  - Emits standardized error responses and controls ack/nack policy.

## Mode Implementations

### Batch (`src/core/batch.py`)

- Uses `MatlabSimulator` (MATLAB Engine API).
- Orders inputs against MATLAB function signature when possible.
- Sends optional progress frames and final success/error response.
- Records startup/simulation/result timing via performance monitor.

### Streaming (`src/core/streaming.py`)

- Starts TCP server, launches MATLAB process, sends initial input payload.
- Receives newline-delimited JSON frames from MATLAB wrapper.
- Converts frames to response templates (`progress`/`streaming`) and forwards to RabbitMQ.
- Sends terminal completion frame with metadata.

### Interactive (`src/core/interactive.py`)

- Creates two TCP servers:
  - output stream (MATLAB -> agent)
  - input stream (agent -> MATLAB)
- Launches MATLAB process and exchanges handshake frame.
- Subscribes to dynamic input stream via `ex.input.stream` and request-scoped queue.
- Relays MATLAB JSON outputs back as incremental/complete responses.

## MATLAB Integration Contracts

- `MatlabSimulator` (`src/core/matlab_simulator.py`)
  - Handles MATLAB engine lifecycle.
  - Converts Python inputs to MATLAB types and back.
  - Extracts ordered argument names from MATLAB function signature.
- Wrapper scripts (`resources/SimulationWrapperStreaming.m`, `SimulationWrapperInteractive.m`)
  - Define socket protocol details and startup handshake behavior for non-batch modes.

## Configuration and Templates

- YAML config model validated by `src/utils/config_manager.py`.
- Response shaping centralized in `src/utils/create_response.py`:
  - `success`, `error`, `progress`, `streaming`.
- Error semantics are template-driven (`error_codes`, optional stack trace inclusion).

## Reliability and Observability

- Broker connection retries and persistent RabbitMQ messages.
- Explicit ack/nack decisions in message handling.
- Per-operation metrics (startup/simulation/total duration + CPU/memory) exported to CSV when enabled.

## Design Tradeoffs

- Shared communication and response-template patterns mirror other agents (SIMUL8), reducing integration friction with the bridge.
- Mode-specific controllers isolate complexity:
  - batch is engine-call oriented,
  - streaming/interactive are socket/process oriented.
- RabbitMQ remains the canonical integration surface with Simulation Bridge and external clients.
