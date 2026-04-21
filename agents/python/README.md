# Python Agent

The Python Agent executes generic script/program files using CLI parameters received in batch simulation requests.

## What it does

- receives a batch simulation message from RabbitMQ
- loads `simulation.file` from the configured simulation path
- maps `simulation.inputs` to CLI arguments
- executes the command
- captures stdout/stderr/exit code and forwards them to the caller

## Quick start

```bash
cd agents/python
poetry install
poetry run python-agent --generate-config
poetry run python-agent --generate-project
poetry run python-agent --config-file config.yaml
```

Generated scaffold:
- `scripts/example_cli_program.py` (sample CLI program)
- `client/use_python_agent_batch.py` (simple publisher)
- `client/simulation.yaml` (example request payload)
