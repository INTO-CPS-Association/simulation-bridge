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

# Code Coverage Report

| File                                               | Statements | Missing | Excluded | Coverage |
| -------------------------------------------------- | ---------- | ------- | -------- | -------- |
| matlab_agent/src/core/matlab_simulator.py          | 91         | 14      | 0        | 85%      |
| matlab_agent/src/core/streaming.py                 | 158        | 21      | 0        | 87%      |
| matlab_agent/src/comm/connect.py                   | 66         | 8       | 0        | 88%      |
| matlab_agent/src/core/agent.py                     | 41         | 4       | 0        | 90%      |
| matlab_agent/tests/test_streaming.py               | 137        | 13      | 0        | 91%      |
| matlab_agent/src/comm/rabbitmq/message_handler.py  | 85         | 7       | 0        | 92%      |
| matlab_agent/src/comm/rabbitmq/rabbitmq_manager.py | 119        | 9       | 0        | 92%      |
| matlab_agent/src/utils/config_manager.py           | 115        | 7       | 0        | 94%      |
| matlab_agent/src/utils/config_loader.py            | 62         | 3       | 0        | 95%      |
| matlab_agent/src/main.py                           | 29         | 1       | 0        | 97%      |
| matlab_agent/tests/test_batch.py                   | 174        | 2       | 0        | 99%      |
| matlab_agent/tests/test_rabbitmq_manager.py        | 111        | 1       | 0        | 99%      |
| matlab_agent/src/**init**.py                       | 0          | 0       | 0        | 100%     |
| matlab_agent/src/comm/**init**.py                  | 0          | 0       | 0        | 100%     |
| matlab_agent/src/comm/interfaces.py                | 22         | 0       | 0        | 100%     |
| matlab_agent/src/comm/rabbitmq/**init**.py         | 0          | 0       | 0        | 100%     |
| matlab_agent/src/comm/rabbitmq/interfaces.py       | 25         | 0       | 0        | 100%     |
| matlab_agent/src/core/**init**.py                  | 0          | 0       | 0        | 100%     |
| matlab_agent/src/core/batch.py                     | 78         | 0       | 0        | 100%     |
| matlab_agent/src/interfaces/**init**.py            | 0          | 0       | 0        | 100%     |
| matlab_agent/src/interfaces/agent.py               | 11         | 0       | 0        | 100%     |
| matlab_agent/src/interfaces/config_manager.py      | 9          | 0       | 0        | 100%     |
| matlab_agent/src/utils/**init**.py                 | 0          | 0       | 0        | 100%     |
| matlab_agent/src/utils/create_response.py          | 45         | 0       | 0        | 100%     |
| matlab_agent/src/utils/logger.py                   | 31         | 0       | 0        | 100%     |
| matlab_agent/tests/**init**.py                     | 0          | 0       | 0        | 100%     |
| matlab_agent/tests/test_agent.py                   | 79         | 0       | 0        | 100%     |
| matlab_agent/tests/test_config_loader.py           | 93         | 0       | 0        | 100%     |
| matlab_agent/tests/test_config_manager.py          | 49         | 0       | 0        | 100%     |
| matlab_agent/tests/test_connect.py                 | 85         | 0       | 0        | 100%     |
| matlab_agent/tests/test_create_response.py         | 113        | 0       | 0        | 100%     |
| matlab_agent/tests/test_logger.py                  | 72         | 0       | 0        | 100%     |
| matlab_agent/tests/test_main.py                    | 86         | 0       | 0        | 100%     |
| matlab_agent/tests/test_matlab_simulator.py        | 130        | 0       | 0        | 100%     |
| matlab_agent/tests/test_message_handler.py         | 99         | 0       | 0        | 100%     |
| **Total**                                          | **2215**   | **90**  | **0**    | **96%**  |
