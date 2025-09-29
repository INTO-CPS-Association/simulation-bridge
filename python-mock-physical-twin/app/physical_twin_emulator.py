"""
IoT Device Emulator

This script emulates IoT devices based on configurations provided in a YAML file. It supports
loading configurations for various protocols such as HTTP and MQTT, creating IoT devices with
sensors and actuators, and starting them to simulate their behavior.

Dependencies:
    - yaml: for parsing YAML configuration files.
    - time: for managing time-related operations.
    - argparse: for parsing command-line arguments.

Imports:
    - Sensor, Actuator, IoTDevice: Classes for defining sensors, actuators, and IoT devices.
    - HttpProtocol, MqttProtocol: Classes for implementing HTTP and MQTT protocols.
    - ProtocolType: Enum defining different protocol types.

Functions:
    - load_devices_from_yaml(yaml_file): Loads device configurations from a YAML file.
    - main(config_file): Main function to initialize protocols, devices, and start their emulation.

Usage:
    The script accepts a command-line argument (-c/--config) specifying the path to a YAML configuration file.
    Example usage: python emulator.py -c config.yaml

Behavior:
    - Loads protocols and devices configurations from the specified YAML file.
    - Initializes and starts protocols (HTTP or MQTT) based on the configuration.
    - Creates IoT devices with specified sensors and actuators, using the configured protocol.
    - Starts all protocols and devices in emulation mode.
    - Handles KeyboardInterrupt to gracefully stop and terminate all running devices and protocols.

"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
import time
import argparse

from app.device.sensor import Sensor
from app.device.actuator import Actuator
from app.device.iot_device import IoTDevice
from app.protocol.http_protocol import HttpProtocol
from app.protocol.mqtt_protocol import MqttProtocol
from app.protocol.simulation_bridge_amqp_protocol import SimulationBridgeAMQPProtocol
from app.utils.emulator_utils import ProtocolType


def load_devices_from_yaml(yaml_file):
    """
    Loads device configurations from a YAML file.

    Args:
        yaml_file (str): Path to the YAML configuration file.

    Returns:
        dict: Dictionary containing the loaded configuration.
    """
    with open(yaml_file, 'r') as file:
        config = yaml.safe_load(file)
    return config


def main(config_file):
    """
    Main function to initialize and run the IoT device emulator based on the provided configuration.

    Args:
        config_file (str): Path to the YAML configuration file.
    """

    # Load configuration from YAML file
    config = load_devices_from_yaml(config_file)

    config_dir = os.path.dirname(os.path.abspath(config_file))
    simulation_bridge_config_raw = config.get('simulation_bridge', {})
    simulation_bridge_config = {}
    for key, value in simulation_bridge_config_raw.items():
        if key in {'client_config', 'simulation_api'} and isinstance(value, str):
            if not os.path.isabs(value):
                simulation_bridge_config[key] = os.path.abspath(os.path.join(config_dir, value))
            else:
                simulation_bridge_config[key] = value
        else:
            simulation_bridge_config[key] = value

    def resolve_simulation_bridge_reference(value):
        if not isinstance(value, str):
            return value
        references = {
            '${simulation_bridge.client_config}': simulation_bridge_config.get('client_config'),
            '${simulation_bridge.simulation_api}': simulation_bridge_config.get('simulation_api'),
        }
        resolved_value = references.get(value)
        return resolved_value if resolved_value else value

    protocol_dict = {}
    device_dict = {}
    config_dir = os.path.dirname(os.path.abspath(config_file))

    # Extract Supported and Configured Protocols
    for protocol_config in config['protocols']:
        protocol_config.setdefault('config', {})
        protocol_config['config'].setdefault('base_path', config_dir)

        # HTTP Protocol Support
        if protocol_config["type"] == ProtocolType.HTTP_PROTOCOL_TYPE.value:
            resolved_config = {
                key: resolve_simulation_bridge_reference(val)
                for key, val in protocol_config["config"].items()
            }
            protocol = HttpProtocol(protocol_id=protocol_config["id"],
                                    device_dict=device_dict,
                                    config=protocol_config["config"])
            protocol_dict[protocol.id] = protocol
        # MQTT Protocol Support
        elif protocol_config["type"] == ProtocolType.MQTT_PROTOCOL_TYPE.value:
            resolved_config = {
                key: resolve_simulation_bridge_reference(val)
                for key, val in protocol_config["config"].items()
            }
            protocol = MqttProtocol(protocol_id=protocol_config["id"],
                                    device_dict=device_dict,
                                    config=protocol_config["config"])
            protocol_dict[protocol.id] = protocol
        elif protocol_config["type"] == ProtocolType.SIMULATION_BRIDGE_AMQP_PROTOCOL_TYPE.value:
            protocol = SimulationBridgeAmqpProtocol(
                protocol_id=protocol_config["id"],
                device_dict=device_dict,
                config=protocol_config["config"],
            )
            protocol_dict[protocol.id] = protocol
        else:
            print(f'Protocol Type not found ! Wrong Type: {protocol_config["type"]}')

    if len(protocol_dict) == 0:
        print("No Supported protocols found! Please check the configuration ...")
        return

    # Extract and Build Devices
    for device_config in config['devices']:
        sensors = [Sensor(**sensor) for sensor in device_config['sensors']]
        actuators = [Actuator(**actuator) for actuator in device_config['actuators']]
        device = IoTDevice(
            device_id=device_config['id'],
            sensors=sensors,
            actuators=actuators,
            protocol=protocol_dict[device_config['protocol_id']],
            independent_communication=config['independent_communication'],
            device_update_delay_ms=config['device_update_delay_ms'])
        device_dict[device.id] = device

    # Start Protocols
    for protocol in protocol_dict.values():
        protocol.start()

    # Start Devices
    for device in device_dict.values():
        device.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for device in device_dict.values():
            device.stop()
        for device in device_dict.values():
            device.join()
        for protocol in protocol_dict.values():
            protocol.stop()


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run IoT devices using configuration from YAML file')
    parser.add_argument('-c', '--config', type=str, metavar='', required=True, help='Path to the YAML configuration file')
    args = parser.parse_args()

    # Call main function with the provided configuration file
    main(args.config)
