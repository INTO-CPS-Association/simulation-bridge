# GitHub Copilot Instructions for simulation-bridge

## Project Overview

This repository contains a Python-based distributed simulation middleware and simulator agents:

- `simulation_bridge/`: protocol-bridging runtime (REST, MQTT, RabbitMQ, in-memory API)
- `agents/matlab/`: MATLAB simulation agent (batch/streaming/interactive)
- `agents/simul8/`: SIMUL8 simulation agent (batch, Windows/COM focused)
- `performance/`: analysis utilities for generated bridge performance metrics

The system uses RabbitMQ as the common routing backbone between bridge and agents.

## Repository Structure

```text
simulation-bridge/
├── simulation_bridge/            # bridge package
│   ├── src/core/                 # orchestrator, core routing, infra setup
│   ├── src/protocol_adapters/    # rest/mqtt/rabbitmq/inmemory adapters
│   ├── src/utils/                # config, logging, signals, perf, certs
│   ├── config/                   # default config templates
│   └── test/                     # unit/integration tests
├── agents/
│   ├── matlab/                   # MATLAB agent package + tests/resources
│   └── simul8/                   # SIMUL8 agent package + tests/resources
├── performance/                  # overhead analysis scripts
└── .github/workflows/            # per-component CI pipelines
```

## Core Engineering Expectations

- Preserve message contract compatibility (`simulation` payloads, routing keys, response fields).
- Keep protocol adapters thin and put routing/business logic in core components.
- Prefer config-driven behavior over hardcoded values.
- Keep error handling explicit (publish structured errors instead of silent drops).
- Maintain existing logging and performance instrumentation patterns.

## Python Style and Tooling

- Python packaging is Poetry-based for root and each agent.
- Existing style signals in repo:
  - `.pep8`: max line length 80
  - `pylintrc`: enforced in CI (`--fail-under=9` in workflows)
- Existing tests are pytest-based and already organized per component.

## How to Work in Each Area

### `simulation_bridge/`

- `BridgeOrchestrator` handles lifecycle, adapter loading, and signal wiring.
- `BridgeCore` is the central request/result router.
- Protocol wiring is defined in `src/protocol_adapters/*.json`; keep adapter class paths and signal names consistent.
- REST adapter includes JWT verification and NDJSON streaming behavior; preserve those contracts.

### `agents/matlab/`

- `MessageHandler` is the dispatch point by `simulation.type`.
- Batch mode uses MATLAB Engine; streaming/interactive use MATLAB subprocess + TCP wrappers.
- Keep response formatting centralized through `create_response`.
- Interactive mode depends on `inputs.stream_source` and `ex.input.stream` routing.

### `agents/simul8/`

- Windows-specific COM automation (`win32com`, `pythoncom`) is core to runtime behavior.
- Avoid Linux-only assumptions in SIMUL8 code paths.
- Preserve CSV input/output contract used by SIMUL8 Visual Logic files.

## Testing and Validation Commands

Use the existing commands already encoded in repo docs/workflows.

### Root (`simulation_bridge`)

```bash
poetry install --with dev
poetry run pylint simulation_bridge --fail-under=9
poetry run pytest
```

### MATLAB agent

```bash
cd agents/matlab
poetry install --with dev
poetry run pylint matlab_agent --fail-under=9
poetry run pytest
```

### SIMUL8 agent

```bash
cd agents/simul8
poetry install --with dev
poetry run pylint simul8_agent --fail-under=9
poetry run pytest
```

## Configuration and Security Notes

- Keep secrets out of committed YAML files; use env substitution patterns where available.
- Preserve TLS toggles and certificate handling logic in bridge and clients.
- Do not weaken JWT checks in REST adapter.
- Keep RabbitMQ durability and ack/nack semantics intact unless explicitly redesigning them.

## When Generating or Refactoring Code

- Reuse existing utilities (`ConfigManager`, `PerformanceMonitor`, `create_response`, logger helpers).
- Follow current folder conventions (`src/core`, `src/comm`, `src/utils`, `test/unit`, `test/integration`).
- Add or update tests in the same component whenever behavior changes.
- Keep changes component-scoped (bridge vs MATLAB agent vs SIMUL8 agent) unless cross-component contract changes are required.
