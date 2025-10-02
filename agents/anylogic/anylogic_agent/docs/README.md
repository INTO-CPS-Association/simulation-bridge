# AnyLogic Simulation – Guidelines and Best Practices

## Streaming Simulation

A Streaming simulation is designed to receive a predefined input configuration at startup and continuously produce real-time outputs during execution. These outputs reflect the internal state of the simulation at each step and are made available to external systems (e.g., The Simulation Bridge) without halting the simulation.

### Streaming Requirements

For this type of simulation, you must use the template given to develop the simulation and import the `BridgeConnection` agent, which should be placed inside the `Main` agent. The `BridgeConnection` handles the UDP connection and communication with the AnyLogic agent.

The `BridgeConnection` agent contains three parameters that are rispectively the ip address, the local port and the remote port to which it publishes the messages and it contains a variable not yet initialized called `communicator`. On the simulation startup `BridgeConnection` executes the following code: 

```java
try {
	this.communicator = new UDPCommunicator(ip, localPort, remotePort);
	this.communicator.setParser(new JsonParser());
	this.communicator.addListener(this::onMessageFromBridge, Map.of());
}
catch (UnknownHostException e){
	error(e, "Unknown host: "+ip);
}
catch (SocketException e) {
	error(e, "Socket error");
}
```

`onMessageFromBridge` is a function inside `BridgeConnection` that handles the receiving of messages from external systems (e.g., The Simulation Bridge) to the simulation. `BridgeConnection` contains another function called `onMessageReceived` that handles the sending of messages from the simulation to external systems.

To access the function that sends messages to external systems by any model's agent call the `connections.send()` function by passing to it the payload of the message as `Map<string, object>` and the receiver that is an agent (e.g., BridgeConnection) that handles the forward of the messages to external systems. `connections.send()` is an intrinsic AnyLogic function that allows the communication between different model's agents thanks to an element called `connections` that is a common channel that links all the model's agent. Once `connections` receives a message from an agent it executes the code contained in the `On message received` window (e.g., call `onMessageReceived` function).

#### Example

Below there is an example :

```java
connections.send(Map.of("message_type", "simulation update", "occurren_event", "item generated", "data", Map.of("x", getX(), "y", getY())), bridgeConnection);
```

In this example:

- Message payload: Map.of("message_type", "simulation update", "occurren_event", "item_generated", "data", Map.of("x", getX(), "y", getY()))
- Receiver: bridgeConnection

Pay attention to the notation of AnyLogic key-value: in the given example key = message_type, value=simulation update.

The map of the strings and objects can be customized as needed, provided they follow the required function signature.

#### References

For additional guidance, refer to the example files located in the `examples/` folder:

- `smart_factory/simulation.alp`
- `smart_factory_4.0/simulation.alp`

These files provide reference implementations that can help in structuring your simulation logic.

#### Notes

No additional constraints are imposed on the implementation. The function should be designed to meet the specific requirements of the simulation scenario.