# IoT Device Emulator

This project is an IoT device emulator designed to simulate devices with
various sensors and actuators using different communication protocols (HTTP, MQTT).
It reads configurations from YAML files to define devices and their behaviors.

## Getting Started

To run the IoT device emulator, follow these steps:

### Prerequisites

- Python>3.13 installed on your system.
- Required Python packages installed:

```bash
pip install -r requirements.txt
```

### Configuration

The emulator uses YAML configuration files to define protocols and devices together with
their sensors and actuators.

Main configuration options are the following:

- **protocol:** Allow to define a list of protocols adapters (e.g., HTTP or MQTT) to be then associated to configured
  devices to communicate according to the specific protocol pattern (e.g., Request/Response or Pub/Sub).
- **devices:** The list of IoT that should be emulated by the application. For each device it is possible to configure
  different sensors and actuators (as described in the next sections).
- **independent_communication:** Allow to specify if each sensor or actuator should be handled in a independent way. If
  True when a new telemetry data is available it will be immediately sent or exposed according to the configured protocol
  and the configured `update_time_ms` parameter of the sensor. Otherwise, if it is false, all the sensor will be handled
  sending or exposing the data with a fixed device driven update time specified through the configuration parameter
  `device_update_delay_ms`.
- **device_update_delay_ms:** Configures the device update time in milliseconds (read the previous parameter description
  for additional details).

#### Sensors

Available Sensor Types are:

- **numeric:** Numeric sensor values randomly generated within a `min_val` and `max_val` and with an `initial_value`.
- **boolean:** Random Boolean values with a configurable `initial_value`.
- **string:**
- **random_string:** d
- **fixed_string:** d

Each sensor has parameter `update_time_ms` allowing to specify the delta time in milliseconds between two value updates.

If for a sensor the paramter `csv_file` is specified with the path to a CSV file (e.g., `data/accelerometer_data_seconds.csv`)
the emulator instead of generating random values will get the values from the CSV columns specified in the configuration
field `value_columns`. If multiple columns of the csv are specified, the values will be aggregated in a single sensor
update (e.g., using `["accel_x", "accel_y", "accel_z"]` each update will contain the 3 accelerometers values).

#### Actuators

Available Sensor Types are:

- **numeric:** Numeric input for the actuator.
- **boolean:** Boolean input for the actuator.
- **string:** String input for the actuator

For each actuator it is also possible to specify the `initial_value` according to its type.
The default management for an actuator is just to log on the console the received message.
If you want to create custom behaviour you can extend the actuator class overriding the method
`handle_action(self, request_type, request_payload)` in order to implement your own logic.
Introducing a new actuator behaviour and class should be handled in the main file in order to properly load the
class according to its new type (that should be declared).

Below are examples of configuration files for HTTP and MQTT protocols (multiple protocols and device configurations
can be used in the same file):

#### HTTP Example Configuration

Details and endpoints related to the RESTful APIs exposed by the implementation are available through a PostMan application
collection in the repository folder [api](api). You can import it in PostMan and test the APIs.

```yaml
protocols:
  - id: "httpProtocol"
    type: "http"
    config:
      server_port: 5555
devices:
  - id: "device1"
    protocol_id: "httpProtocol"
    sensors:
      - id: "numericSensor"
        type: "numeric"
        update_time_ms: 2000 # Update every 2 seconds
        min_val: 0
        max_val: 100
        initial_value: 0
      - id: "booleanSensor"
        type: "boolean"
        update_time_ms: 2000 # Update every 2 seconds
        initial_value: false
      - id: "randomStringSensor"
        type: "random_string"
        value_len: 10
        update_time_ms: 2000 # Update every 2 seconds
      - id: "fixedStringSensor"
        type: "fixed_string"
        value: "test-fixed-string"
        update_time_ms: 2000 # Update every 2 seconds
    actuators:
      - id: "demoActuator"
        type: "string"
        initial_value: "ON"
independent_communication: True
device_update_delay_ms: 10 # Update every 10 seconds if independent_communication is False
```

#### MQTT Example Configuration File

```yaml
protocols:
  - id: "mqttProtocol"
    type: "mqtt"
    config:
      broker_ip: "192.168.1.106"
      broker_port: 1883
      username: null
      password: null
devices:
  - id: "device1"
    protocol_id: "mqttProtocol"
    sensors:
      - id: "fixedStringSensor"
        type: "fixed_string"
        value: "test-fixed-string"
        update_time_ms: 5000
      - id: "sensor_accel"
        type: "numeric"
        update_time_ms: 1000
        csv_file: "data/accelerometer_data_seconds.csv"
        value_columns: ["accel_x", "accel_y", "accel_z"]
    actuators:
      - id: "demoActuator"
        type: "string"
        initial_value: "ON"
independent_communication: True
device_update_delay_ms: 1000 # Update every 10 seconds if independent_communication is False
```

#### MQTT Configuration File with CSV Input

```yaml
protocols:
  - id: "mqttProtocol"
    type: "mqtt"
    config:
      broker_ip: "192.168.1.106"
      broker_port: 1883
      username: null
      password: null
devices:
  - id: "device1"
    protocol_id: "mqttProtocol"
    sensors:
      - id: "fixedStringSensor"
        type: "fixed_string"
        value: "test-fixed-string"
        update_time_ms: 5000
      - id: "sensor_accel"
        type: "numeric"
        update_time_ms: 1000
        csv_file: "data/accelerometer_data_seconds.csv"
        value_columns: ["accel_x", "accel_y", "accel_z"]
    actuators:
      - id: "demoActuator"
        type: "string"
        initial_value: "ON"
independent_communication: True
device_update_delay_ms: 1000 # Update every 10 seconds if independent_communication is False
```

#### Simulation Bridge AMQP Example Configuration

The emulator can forward aggregated device telemetry to the Simulation Bridge via RabbitMQ by
reusing the client templates shipped with the main project. Copy
`simulation_bridge/resources/rabbitmq/rabbitmq_use.yaml.template` and
`simulation_bridge/resources/simulation.yaml.template` to
`rabbitmq_use.yaml` and `simulation.yaml`, then reference them in the protocol configuration:

```yaml
protocols:
  - id: "simulationBridge"
    type: "simulation_bridge_amqp"
    config:
      client_config: "../simulation_bridge/resources/rabbitmq/rabbitmq_use.yaml"
      simulation_api: "../simulation_bridge/resources/simulation.yaml"
      aggregate:
        device_id: "device1"
        sensor_id: "bridgeAggregate"
        sensor_config:
          type: "string"
          update_time_ms: 1000
devices:
  - id: "device1"
    protocol_id: "simulationBridge"
    sensors:
      - id: "bridgeAggregate"
        type: "string"
        update_time_ms: 60000
        initial_value: {}
    actuators: []
independent_communication: False
device_update_delay_ms: 1000
```

The `aggregate` section identifies the device and sensor that will store the simulation
results. If the sensor is not already declared under the device, the optional
`sensor_config` block is used to create it at runtime.

### Running the Emulator

To start the IoT device emulator, run the `physical_twin_emulator.py` script
with the configuration file path specified using the -c or --config option:

```bash
python physical_twin_emulator.py -c http_test_config.yaml
```
