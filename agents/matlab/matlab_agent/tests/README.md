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
