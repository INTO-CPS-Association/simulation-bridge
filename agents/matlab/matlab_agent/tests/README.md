# Tests Documentation

This folder contains all the tests for the `src/` directory of the MATLAB agent project. The tests are written using `pytest` and `unittest.mock` to thoroughly verify the functionality of each file inside the `src/` folder.

## Running the Tests

To execute the tests, navigate to the main project directory (`agents/matlab`) and run:

```bash
pytest -v
```

Alternatively, if you are using the **Testing Extension for VSCode**, you need to configure the `settings.json` inside the `.vscode` folder at the root of the project as follows:

```json
{
  "python.testing.pytestArgs": ["."],
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "python.testing.cwd": "${workspaceFolder}/agents/matlab",
  "python.testing.autoTestDiscoverOnSaveEnabled": true
}
```

This will allow VSCode to automatically detect and run your tests every time you save changes.

## Coverage Report

The following table provides a detailed coverage report for the MATLAB agent project.

| File                                            | Statements | Missing | Excluded | Coverage |
| ----------------------------------------------- | ---------- | ------- | -------- | -------- |
| matlab_agent/src/batch/matlab_simulator.py      | 89         | 20      | 0        | 78%      |
| matlab_agent/src/streaming/streaming.py         | 158        | 21      | 0        | 87%      |
| matlab_agent/tests/test_streaming.py            | 137        | 13      | 0        | 91%      |
| matlab_agent/src/core/config_manager.py         | 115        | 7       | 0        | 94%      |
| matlab_agent/src/batch/batch.py                 | 77         | 4       | 0        | 95%      |
| matlab_agent/src/utils/config_loader.py         | 62         | 3       | 0        | 95%      |
| matlab_agent/tests/test_core_integration.py     | 80         | 4       | 0        | 95%      |
| matlab_agent/src/main.py                        | 28         | 1       | 0        | 96%      |
| matlab_agent/tests/test_message_handler.py      | 145        | 5       | 0        | 97%      |
| matlab_agent/tests/test_rabbitmq_manager.py     | 123        | 4       | 0        | 97%      |
| matlab_agent/src/handlers/message_handler.py    | 84         | 1       | 0        | 99%      |
| matlab_agent/src/**init**.py                    | 0          | 0       | 0        | 100%     |
| matlab_agent/src/batch/**init**.py              | 0          | 0       | 0        | 100%     |
| matlab_agent/src/core/**init**.py               | 0          | 0       | 0        | 100%     |
| matlab_agent/src/core/agent.py                  | 42         | 0       | 0        | 100%     |
| matlab_agent/src/core/rabbitmq_manager.py       | 97         | 0       | 0        | 100%     |
| matlab_agent/src/handlers/**init**.py           | 0          | 0       | 0        | 100%     |
| matlab_agent/src/interfaces/**init**.py         | 0          | 0       | 0        | 100%     |
| matlab_agent/src/interfaces/agent.py            | 11         | 0       | 0        | 100%     |
| matlab_agent/src/interfaces/config_manager.py   | 9          | 0       | 0        | 100%     |
| matlab_agent/src/interfaces/message_handler.py  | 9          | 0       | 0        | 100%     |
| matlab_agent/src/interfaces/rabbitmq_manager.py | 19         | 0       | 0        | 100%     |
| matlab_agent/src/streaming/**init**.py          | 0          | 0       | 0        | 100%     |
| matlab_agent/src/utils/**init**.py              | 0          | 0       | 0        | 100%     |
| matlab_agent/src/utils/create_response.py       | 45         | 0       | 0        | 100%     |
| matlab_agent/src/utils/logger.py                | 31         | 0       | 0        | 100%     |
| matlab_agent/tests/**init**.py                  | 0          | 0       | 0        | 100%     |
| matlab_agent/tests/test_agent.py                | 60         | 0       | 0        | 100%     |
| matlab_agent/tests/test_batch.py                | 114        | 0       | 0        | 100%     |
| matlab_agent/tests/test_config_loader.py        | 93         | 0       | 0        | 100%     |
| matlab_agent/tests/test_config_manager.py       | 49         | 0       | 0        | 100%     |
| matlab_agent/tests/test_create_response.py      | 113        | 0       | 0        | 100%     |
| matlab_agent/tests/test_logger.py               | 72         | 0       | 0        | 100%     |
| matlab_agent/tests/test_main.py                 | 86         | 0       | 0        | 100%     |
| **Total**                                       | **1948**   | **83**  | **0**    | **96%**  |
