# Copilot Instructions for `simulation-bridge`

## Build, test, lint, and package commands

### Root package (`simulation_bridge/`)

Run from repository root:

```bash
poetry install --with dev
poetry run autopep8 --recursive --diff simulation_bridge
poetry run autopep8 --in-place --aggressive --recursive simulation_bridge
poetry run pylint simulation_bridge --fail-under=9
poetry run pytest
poetry run pytest simulation_bridge/test/unit/test_bridge_core.py
poetry run pytest simulation_bridge/test/unit/test_bridge_core.py::TestHandleInputMessage::test_handle_input_message_valid
poetry run pytest simulation_bridge/test/integration/
poetry build --format wheel
poetry build --format sdist
```

Key CI reference: `.github/workflows/simulation-bridge-ci.yml`.

### MATLAB agent (`agents/matlab`)

Run from `agents/matlab`:

```bash
poetry install --with dev
poetry run autopep8 --recursive --diff matlab_agent
poetry run autopep8 --in-place --aggressive --recursive matlab_agent
poetry run pylint matlab_agent --fail-under=9
poetry run pytest
poetry run pytest matlab_agent/test/unit/test_main.py
poetry run pytest matlab_agent/test/unit/test_batch.py::TestBatchSimulationUtils::test_valid_data
poetry build --format wheel
poetry build --format sdist
```

Key CI reference: `.github/workflows/matlab-agent-ci.yml`.

### Simul8 agent (`agents/simul8`)

Run from `agents/simul8`:

```bash
poetry install --with dev
poetry run autopep8 --recursive --diff simul8_agent
poetry run autopep8 --in-place --aggressive --recursive simul8_agent
poetry run pylint simul8_agent --fail-under=9
poetry run pytest
poetry run pytest simul8_agent/tests/unit/test_main.py
poetry run pytest simul8_agent/tests/unit/test_batch.py::TestBatchSimulationUtils::test_valid_data
poetry build --format wheel
poetry build --format sdist
```

Key CI reference: `.github/workflows/simul8-agent-ci.yml`.

---

## High-level architecture (big picture)

The repository is a message-driven bridge plus simulator-specific agents:

- **Bridge runtime**: `simulation_bridge/src/main.py` starts `BridgeOrchestrator`, which loads config, ensures TLS certs, sets up RabbitMQ infrastructure, instantiates enabled adapters, wires signals, and supervises adapter health.
- **Core routing**: `simulation_bridge/src/core/bridge_core.py` validates incoming simulation payloads (Pydantic), publishes requests to RabbitMQ (`ex.bridge.output`), handles simulator results from RabbitMQ, and republishes results (`ex.bridge.result`) with protocol metadata.
- **Infrastructure bootstrap**: `simulation_bridge/src/core/bridge_infrastructure.py` declares exchanges/queues/bindings from YAML config.
- **Protocol adapters**: `simulation_bridge/src/protocol_adapters/` implements RabbitMQ, MQTT, REST, and InMemory adapters behind the common abstract `ProtocolAdapter`.
- **Signal bus**: `simulation_bridge/src/utils/signal_manager.py` maps events to handlers using Blinker; mappings come from JSON config (`adapters_signal.json` vs `inmemory_signal.json`).
- **Simulator agents**: `agents/matlab` and `agents/simul8` are independent Poetry projects that consume bridge commands from RabbitMQ and publish results back.

Primary flow (normal mode): client protocol adapter -> signal -> `BridgeCore.handle_input_message` -> RabbitMQ exchange/route -> simulator agent queue -> simulator execution -> result exchange -> bridge -> fan-out to REST/MQTT/RabbitMQ/in-memory destination.

Primary flow (in-memory mode): `simulation_bridge.SimulationBridge` uses in-process callbacks while still routing through `BridgeCore` logic.

---

## Key repository conventions

### Message schema and routing conventions

- Request payloads use top-level `simulation` with fields such as `request_id`, `client_id`, `simulator`, `type`, `file`, `inputs`, `outputs` (see `simulation_bridge/resources/simulation.yaml.template`).
- Bridge writes protocol provenance to `simulation.bridge_meta.protocol`; downstream result fan-out relies on this metadata.
- Bridge RabbitMQ routing key for input publish is `"{producer}.{consumer}"`.
- Agent queues are named `Q.sim.<agent_id>` and are bound to input exchange with `*.{agent_id}` (e.g., MATLAB/Simul8 managers).
- Agent result payloads include `source` and `destinations` and are sent to `ex.sim.result`.

### Signal-driven dispatch is config-backed

- Signal bindings are not hardcoded in one place; they are loaded from JSON (`adapters_signal.json` / `inmemory_signal.json`) and connected dynamically.
- `simulation_bridge.in_memory_mode` changes which signal map is loaded (`load_protocol_config`), so behavior depends on config, not just code path.

### Configuration behavior to preserve

- Runtime config is validated by nested Pydantic models in `utils/config_manager.py`.
- YAML supports environment substitution in string values with `${VAR}` and `${VAR:default}` (`utils/config_loader.py`).
- If config load/validation fails, `ConfigManager` falls back to internal defaults; avoid assuming missing config is fatal.

### Security and transport conventions

- TLS enablement is per protocol (`rabbitmq.tls`, `mqtt.tls`, REST cert/key fields), and bridge startup auto-generates certs when needed (`utils/certs.py`).
- REST adapter expects JWT Bearer tokens, validates header/algorithm/claims, and enforces token age (`rest/rest_adapter.py`).

### Test layout is intentionally inconsistent across packages

- Root tests live under `simulation_bridge/test/...`.
- MATLAB agent tests use singular `test/` directory.
- Simul8 agent tests use plural `tests/` directory.

Use package-local `pytest.ini` and working directory when running agent tests to avoid path/coverage confusion.
