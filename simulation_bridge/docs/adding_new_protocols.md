# Adding New Protocol Adapters

This guide explains how to add new protocol adapters to the Simulation Bridge

## Overview

The Simulation Bridge uses a modular architecture for protocol adapters. Each adapter is responsible for:

- Handling communication with a specific protocol (e.g., MQTT, RabbitMQ, REST)
- Converting messages between the protocol's format and the bridge's internal format
- Managing protocol-specific connections and resources

## Directory Structure

Protocol adapters are organized in the following structure:

```
simulation_bridge/src/protocol_adapters/
├── base/
│   └── protocol_adapter.py    # Base abstract class
├── rabbitmq/
│   └── rabbitmq_adapter.py    # RabbitMQ implementation
├── mqtt/
│   └── mqtt_adapter.py        # MQTT implementation
└── rest/
    └── rest_adapter.py        # REST implementation
```

## Steps to Add a New Protocol Adapter

1. **Create a New Directory**
   Create a new directory under `protocol_adapters/` for your protocol:

   ```bash
   mkdir simulation_bridge/src/protocol_adapters/your_protocol
   ```

2. **Create the Adapter Class**
   Create a new file `*_adapter.py` in your protocol's directory:

   ```python
   from ..base.protocol_adapter import ProtocolAdapter
   from ...utils.config_manager import ConfigManager
   from typing import Dict, Any

   class YourProtocolAdapter(ProtocolAdapter):
       def _get_config(self) -> Dict[str, Any]:
           return self.config_manager.get_your_protocol_config()

       def start(self) -> None:
           # Implement protocol-specific startup logic
           pass

       def stop(self) -> None:
           # Implement protocol-specific shutdown logic
           pass

       def _handle_message(self, message: Dict[str, Any]) -> None:
           # Implement message handling logic
           pass
   ```

3. **Add Configuration**

   - Add your protocol's configuration section to `config.yaml.template`
   - Update the `ConfigManager` class to include your protocol's configuration

4. **Register the Adapter**
   Add your adapter to the registry in `BridgeOrchestrator`:
   ```python
   self.adapter_classes = {
       'rabbitmq': RabbitMQAdapter,
       'mqtt': MQTTAdapter,
       'rest': RESTAdapter,
       'your_protocol': YourProtocolAdapter,  # Add your adapter here
   }
   ```

## Required Methods

Your adapter must implement these methods from the `ProtocolAdapter` base class:

1. `_get_config()`: Returns your protocol's configuration
2. `start()`: Handles protocol-specific startup
3. `stop()`: Handles protocol-specific shutdown
4. `_handle_message()`: Processes incoming messages

## Best Practices

1. **Error Handling**

   - Implement proper error handling for network issues
   - Log errors appropriately
   - Handle reconnection scenarios

2. **Resource Management**

   - Clean up resources in the `stop()` method
   - Handle connection timeouts
   - Implement proper connection pooling if needed

3. **Message Format**

   - Convert protocol-specific messages to the bridge's internal format (Rabbitmq), see [internal architecture](./internal_architecture.md)

   - Handle message validation
   - Implement proper error responses

4. **Testing**
   - Write unit tests for your adapter
   - Test error scenarios
   - Test reconnection logic
