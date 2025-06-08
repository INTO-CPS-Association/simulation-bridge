# Simulation Bridge Internal Architecture

The Simulation Bridge is designed according to an event-driven architecture. Each simulation request is transformed into an independent event, enabling asynchronous and non-blocking process management. Converting requests into events allows decoupling the communication flow between clients and simulators.

![Event-based Architecture](../../images/event_based_sm.png)

## Message Flow

```mermaid
sequenceDiagram
                participant DT as Digital Twin<br/>(REST)
                participant MockPT as Mock Physical Twin<br/>(RabbitMQ)
                participant PT as Physical Twin<br/>(MQTT)
                participant Bridge as Simulation Bridge
                participant SimA as Simulator A
                participant SimB as Simulator B

                rect rgba(46, 64, 83, 0.1)
                                Note over DT,Bridge: REST Flow Example
                                DT->>+Bridge: Send Request (REST)
                                Note right of Bridge: Parse & convert to internal format
                                Bridge->>+SimA: Forward Request
                                SimA-->>-Bridge: Return Response
                                Note right of Bridge: Convert to REST format
                                Bridge-->>-DT: Deliver Response (REST)
                end

                rect rgba(39, 174, 96, 0.1)
                                Note over MockPT,Bridge: RabbitMQ Flow Example
                                MockPT->>+Bridge: Send Request (RabbitMQ)
                                Note right of Bridge: Parse & convert to internal format
                                Bridge->>+SimB: Forward Request
                                SimB-->>-Bridge: Return Response
                                Note right of Bridge: Convert to RabbitMQ format
                                Bridge-->>-MockPT: Deliver Response (RabbitMQ)
                end

                rect rgba(142, 68, 173, 0.1)
                                Note over PT,Bridge: MQTT Flow Example
                                PT->>+Bridge: Send Request (MQTT)
                                Note right of Bridge: Parse & convert to internal format
                                Bridge->>+SimA: Forward Request
                                SimA-->>-Bridge: Return Response
                                Note right of Bridge: Convert to MQTT format
                                Bridge-->>-PT: Deliver Response (MQTT)
                end
```

## Signal System

The Simulation Bridge implements an event-driven message dispatching system using Blinker for internal signal routing across protocols.

The `SignalManager` class (located in `utils/signal_manager.py`) serves as the central component for managing signal flow:

- Automatically loads signal definitions from protocol configuration files (e.g., `adapters_signal.json`)
- Registers all protocol adapters and the `BridgeCore` instance
- Maps signal names (e.g., `message_received_input_mqtt`) to their corresponding handler methods (e.g., `BridgeCore.handle_input_message`)
- Facilitates clean disconnection of all signals during shutdown
- Provides comprehensive logging for debugging and traceability

This approach effectively decouples protocol-specific logic from the core business logic, enabling flexible signal routing based on the configured architecture.

### Protocol Signal Reference

| Protocol | Available Signals                                                       |
| -------- | ----------------------------------------------------------------------- |
| RabbitMQ | `message_received_input_rabbitmq`<br>`message_received_result_rabbitmq` |
| MQTT     | `message_received_input_mqtt`<br>`message_received_result_mqtt`         |
| REST     | `message_received_input_rest`<br>`message_received_result_rest`         |

## Threading Model

The system uses a multi-threaded architecture:

- Each adapter runs in its own thread
- Main thread monitors adapter health
- Clean shutdown mechanism
