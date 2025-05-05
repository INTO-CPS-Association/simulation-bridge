### Project Structure

```
src/
└── simulation_bridge/
    ├── core/
    |   ├── config/
    |   |   └── config.yaml
    │   ├── __init__.py
    |   ├── main.py
    │   └── simulation_bridge_core.py
    ├── protocol_adapters/
    │   ├── __init__.py
    │   ├── base_adapter.py
    │   ├── rabbitmq_adapter.py
    │   ├── mqtt_adapter.py
    │   └── rest_adapter.py
    ├── connectors/
    │   ├── __init__.py
    │   ├── base_connector.py
    │   ├── matlab_connector.py
    ├── data_transformation/
    │   ├── __init__.py
    │   ├── transformation_manager.py
    │   ├── json_transformer.py
    │   ├── xml_transformer.py
    |   ├── base_transformer.py
    │   └── csv_transformer.py
    ├── configuration/
    │   ├── __init__.py
    │   ├── config_manager.py
    │   └── config_schemas.py
    ├── management_interface/
    │   ├── __init__.py
    │   └── interface.py
    ├── models/
    │   ├── __init__.py
    │   ├── simulation_state.py
    │   └── command_models.py
    ├── utils/
    │   ├── __init__.py
    │   ├── logger.py
    │   └── exceptions.py
    ├──  logs/
    ├──  test/
    └── __init__.py

```
