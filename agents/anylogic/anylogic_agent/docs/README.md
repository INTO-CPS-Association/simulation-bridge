# AnyLogic Simulation – Guidelines and Best Practices

## Batch & Streaming Simulation

> The difference between **Batch** and **Streaming** simulation lies only in the output mode:  
> Batch simulations produce a single result at the end, while Streaming simulations emit results continuously.  
> The development and integration process is otherwise identical for both.

A Streaming simulation is designed to receive a predefined input configuration at startup and continuously produce real-time outputs during execution. These outputs reflect the internal state of the simulation at each step and are made available to external systems (e.g., The Simulation Bridge) without halting the simulation.
N.B. For AnyLogic there is no difference between Batch and Streaming simulation .

> ⚠️ Detailed information about the project template lives [here](agents/anylogic/anylogic_agent/resources/template/README.md)

### New Simulation (from scratch)

#### Steps to Set Up and Run the Streaming Simulation

##### 1. Generate the Project Template

```sh
poetry install
poetry run anylogic-agent --generate-project
```

This creates a `template/` folder containing `template.alp`, `shared.jar`, and a README describing the template structure.

##### 2. Open the Project in AnyLogic

- Open `template/template.alp` in AnyLogic.
- Ensure `shared.jar` is in the same folder; it provides required helper classes.

##### 3. Review the BridgeConnection Component

- In the Main agent, locate the pre-wired `BridgeConnection` component.
- This manages the UDP connection with the AnyLogic Agent.
- See the template README for more details.

##### 4. Implement Your Simulation Logic

- **To send messages outside the model:**

  ```java
  connections.send(payload, bridgeConnection);
  ```

  where `payload` is a `Map<String, Object>` describing the update.

- **To handle incoming messages from the Agent:**
  Implement the function:
  ```java
  void onMessageFromBridge(Map<String, Object> message)
  ```
  inside `BridgeConnection`.

##### 5. Configure Runtime Settings

- Set UDP ports, host, and message frequency in the `BridgeConnection` properties or via parameters in Main.

##### 6. Running the Simulation

- **Start the AnyLogic Agent:**
  - Configure it to use the same UDP ports as your simulation (_config.yaml_).
  - Launch the agent process with:
  ```sh
  poetry run anylogic-agent
  ```
- **Wait for Simulation Requests:**  
   The agent remains idle until a simulation request arrives.  
   Upon receiving a request, it checks for the simulation file and starts a UDP listener to capture results.

- **Run the Simulation in AnyLogic:**  
   Only now, Launch the simulation in AnyLogic.  
   Output messages are sent to `BridgeConnection`, forwarded to the AnyLogic Agent, and then to the connected client (or Simulation Bridge).

> **In summary:**  
> Once the agent is running and the simulation is started in AnyLogic, data will automatically stream from the simulation → BridgeConnection → AnyLogic Agent → client.

Refer to the example files in the `examples/` folder:

- `smart_factory/simulation.alp`
- `robot_golem_manufacturing/golem_simulation.alp`
  These files provide reference implementations to help you structure your simulation logic.

### Existing Simulations integration

To integrate an existing AnyLogic simulation with the AnyLogic Agent, follow these steps:

1. **Open Your Existing Simulation**: Launch AnyLogic and open your existing simulation project.
2. **Add the BridgeConnection Component**: In the Main agent of your simulation, add the `BridgeConnection` component from the template. This component will handle UDP communication with the AnyLogic Agent.
3. **Configure the BridgeConnection**: Set the necessary parameters in the `BridgeConnection` component, such as UDP ports and host settings, to match those configured in the AnyLogic Agent.
4. **Implement Message Handling**: If your simulation needs to send data to or receive data from the AnyLogic Agent, implement the `onMessageFromBridge` function in the `BridgeConnection` component to handle incoming messages. Use the `connections.send()` method to send messages from your simulation.
5. **Test the Integration**: Start the AnyLogic Agent and run your simulation to ensure that data is being correctly sent and received.
6. **Adjust Simulation Logic as Needed**: Depending on your simulation's requirements, you may need to adjust the logic to accommodate real-time data exchange.

## Interactive Simulation

An interactive simulation exchanges messages with the AnyLogic Agent while the model is running. This bidirectional flow lets you react to user input or external systems in real time and push updated state back through the bridge.

### Implement Your Simulation Logic

1. **Handle incoming messages in `BridgeConnection`:**
   Implement the hook provided in the template so that every message from the Agent is captured.

   ```java
   void onMessageFromBridge(Map<String, Object> message)
   ```

2. **Forward messages to `Main`:**
   Inside `onMessageFromBridge`, pass the payload to the `connections` element so the rest of the model can react.

   ```java
   connections.send(message, main);
   ```

3. **Process the message inside `Main`:**
   In the `connections` element of `Main`, read the fields you expect and update the model state accordingly. The snippet below shows how to branch on a custom `variable` field and adjust model parameters.

   ```java
   Map<String, Object> data = (Map<String, Object>) msg.get("data");
   String variable = (String) data.get("variable");

   // Custom logic
   if ("executionTime".equals(variable)) {
     String velocity = (String) data.get("state");
     if ("low".equals(velocity)) {
       this.executionTime = 6;
     } else if ("medium".equals(velocity)) {
       this.executionTime = 4;
     } else if ("high".equals(velocity)) {
       this.executionTime = 2;
     }
   }
   ```

Use this structure to fan out to additional variables, trigger events, or drive agents based on the messages you receive.
