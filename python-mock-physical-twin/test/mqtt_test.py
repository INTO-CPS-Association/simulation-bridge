import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
import time
from app.device.sensor import Sensor
from app.device.actuator import Actuator
from app.device.iot_device import IoTDevice
from app.protocol.mqtt_protocol import MqttProtocol
from app.utils.emulator_utils import ProtocolType


def load_devices_from_yaml(yaml_file):
    with open(yaml_file, 'r') as file:
        config = yaml.safe_load(file)

    return config

    # devices = []
    # for device_config in config['devices']:
    #     sensors = [Sensor(**sensor) for sensor in device_config['sensors']]
    #     actuators = [Actuator(**actuator) for actuator in device_config['actuators']]
    #     protocol = Protocol(**device_config['protocol'])
    #     device = IoTDevice(device_config['id'], sensors, actuators, protocol)
    #     devices.append(device)
    #
    # return devices


if __name__ == "__main__":

    # config = load_devices_from_yaml('conf/mqtt_test_config.yaml')
    config = load_devices_from_yaml('conf/mqtt_acc_config.yaml')

    protocol_dict = {}
    device_dict = {}

    # Extract Supported and Configured Protocols
    for protocol_config in config['protocols']:

        # Build Protocols Adapters according to the declared type
        if protocol_config["type"] == ProtocolType.MQTT_PROTOCOL_TYPE.value:
            protocol = MqttProtocol(protocol_id=protocol_config["id"],
                                    config=protocol_config["config"])
            protocol_dict[protocol.id] = protocol

    if len(protocol_dict) == 0:
        print("No Supported protocols found ! Please check the configuration ...")
    else:
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
