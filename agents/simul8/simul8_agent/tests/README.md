# Tests Documentation

This folder contains all the tests for the `src/` directory of the SIMUL8 agent project.
The tests are written using `pytest` and `unittest.mock` to thoroughly verify
the functionality of each file inside the `src/` folder.

## Running the Tests

To execute the tests,
navigate to the main project directory (`agents/simul8`) and run:

```bash
pytest -v
```

Alternatively, if you are using the **Testing Extension for VSCode**,
you need to configure the `settings.json` inside the `.vscode`
folder at the root of the project as follows:

```json
{
  "python.testing.pytestArgs": ["."],
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "python.testing.cwd": "${workspaceFolder}/agents/simul8",
  "python.testing.autoTestDiscoverOnSaveEnabled": true
}
```
<!--markdownlint-disable-->
This will allow VSCode to automatically detect and run your tests every time you save changes.

## Coverage Report

The following table provides a detailed coverage report for the SIMUL8 agent project.

# Code Coverage Report

| File | Statements | Miss | Cover | Missing |
|---|---:|---:|---:|---:|
| simul8_agent\src\comm\connect.py | 67 | 48 | 28% | |
| simul8_agent\src\comm\interfaces.py | 22 | 0 | 100% | |
| simul8_agent\src\comm\rabbitmq\interfaces.py | 25 | 0 | 100% | |
| simul8_agent\src\comm\rabbitmq\message_handler.py | 98 | 64 | 35% | |
| simul8_agent\src\comm\rabbitmq\rabbitmq_manager.py | 127 | 107 | 16% | |
| simul8_agent\src\core\agent.py | 51 | 7 | 86% | |
| simul8_agent\src\core\batch.py | 93 | 12 | 87% | |
| simul8_agent\src\core\simul8_simulator.py | 247 | 28 | 89% | |
| simul8_agent\src\interfaces\agent.py | 11 | 0 | 100% | |
| simul8_agent\src\interfaces\config_manager.py | 9 | 0 | 100% | |
| simul8_agent\src\main.py | 110 | 2 | 98% | |
| simul8_agent\src\utils\config_loader.py | 65 | 53 | 18% | |
| simul8_agent\src\utils\config_manager.py | 124 | 70 | 44% | |
| simul8_agent\src\utils\create_response.py | 45 | 38 | 16% | |
| simul8_agent\src\utils\csv_parser.py | 113 | 12 | 89% | |
| simul8_agent\src\utils\logger.py | 31 | 0 | 100% | |
| simul8_agent\src\utils\performance_monitor.py | 128 | 58 | 55% | |
| **TOTAL** | **1366** | **499** | **63%** | |
<!--markdownlint-enable-->
