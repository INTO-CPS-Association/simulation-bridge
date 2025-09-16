from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.device.iot_device import IoTDevice
    from typing import Dict

from app.protocol.protocol import Protocol, validate_dict_keys, InvalidConfigurationError
from app.utils.emulator_utils import ProtocolType
import paho.mqtt.client as mqtt
import string
import random
import re


def generate_random_client_id():
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(10))
    return f'mqtt_client_{random_string}'


class MqttProtocol(Protocol):

    ACTION_WILD_CARD = "device/+/actuator/+/action"

    def __init__(self,
                 protocol_id,
                 device_dict: Dict[str, IoTDevice] = None,
                 config: Dict = None):
        super().__init__(protocol_id, ProtocolType.MQTT_PROTOCOL_TYPE, device_dict, config)

        self.broker_ip = self.config['broker_ip']
        self.broker_port = self.config['broker_port']
        self.username = self.config['username']
        self.password = self.config['password']
        self.client_id = generate_random_client_id()
        self.client = None

    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        self.subscribe_for_actions()

    # Define a callback method to receive asynchronous messages
    def on_message(self, client, userdata, message):

        if mqtt.topic_matches_sub(self.ACTION_WILD_CARD, message.topic):
            payload = str(message.payload.decode("utf-8"))
            device_id, actuator_id = self.extract_info_from_action_topic(message.topic)

            if device_id is not None and actuator_id is not None:
                if device_id in self.device_dict.keys() and self.device_dict[device_id].get_actuator_by_id(actuator_id) is not None:
                    self.device_dict[device_id].get_actuator_by_id(actuator_id).handle_action("MQTT_ACTION", payload)
                else:
                    print(f'Device ({device_id}) or Actuator ({actuator_id}) not found ! Nothing to actuate ...')
        else:
            print(f'Received UnKnown Action Message on Topic: {message.topic} with Payload: {str(message.payload.decode("utf-8"))}')

    def extract_info_from_action_topic(self, input_topic):

        # Regular Expression
        pattern = re.compile(r'device/(?P<deviceid>[^/]+)/actuator/(?P<actuatorId>[^/]+)/action')

        # String match
        match = pattern.search(input_topic)

        if match:
            device_id = match.group('deviceid')
            actuator_id = match.group('actuatorId')
            return device_id, actuator_id
        else:
            return None, None

    def start(self):
        print(f'Starting protocol: {self.id} Type: {self.type}')
        print(f'Initializing MQTT client ...')

        # Create MQTT Client
        self.client = mqtt.Client(self.client_id)

        # Set Callback Methods
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # If required sets Username and Password
        if self.username is not None and self.password is not None:
            print(f"Setting Username & Password for MQTT Client Connection. Username: {self.username}")
            self.client.username_pw_set(self.username, self.password)

        # Connect
        self.client.connect(str(self.broker_ip), int(self.broker_port))

        print(f'Connected to Broker: tcp://{self.broker_ip}:{self.broker_port} with ClientId: {self.client_id}')

        # Blocking call that processes network traffic, dispatches callbacks and
        # handles reconnecting.
        # Other loop*() functions are available that give a threaded interface and a
        # manual interface.
        self.client.loop_start()

    def stop(self):
        print(f'Stopping protocol: {self.id} Type: {self.type}')
        self.client.disconnect()
        print(f'Disconnected from MQTT Broker ...')
        pass

    def subscribe_for_actions(self):
        for device in self.device_dict.values():
            for actuator in device.actuators:
                target_topic = "device/{0}/actuator/{1}/action".format(device.id, actuator.id)
                self.client.subscribe(target_topic)
                print(f'Subscribed to topic: {target_topic}')

    def validate_config(self):
        required_keys = ["broker_ip", "broker_port"]
        if not validate_dict_keys(self.config, required_keys):
            raise InvalidConfigurationError(required_keys)

    def publish_sensor_telemetry_data(self, device_id, sensor_id, payload):
        target_topic = "device/{0}/sensor/{1}/telemetry".format(device_id, sensor_id)
        self.client.publish(target_topic, payload, 0, False)

    def publish_device_telemetry_data(self, device_id, payload):
        target_topic = "device/{0}/telemetry".format(device_id)
        self.client.publish(target_topic, payload, 0, False)
