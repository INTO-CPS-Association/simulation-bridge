from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.device.iot_device import IoTDevice
    from typing import Dict

from app.protocol.protocol import Protocol, validate_dict_keys, InvalidConfigurationError
from app.utils.emulator_utils import ProtocolType
from flask import Flask, jsonify, request, abort
import threading


class HttpProtocol(Protocol):

    def __init__(self,
                 protocol_id,
                 device_dict: Dict[str, IoTDevice] = None,
                 config=None):
        super().__init__(protocol_id, ProtocolType.HTTP_PROTOCOL_TYPE, device_dict, config)

        print(f'Initializing HTTP Server to expose devices data ...')

    def start(self):
        print(f'Starting protocol: {self.id} Type: {self.type}')

        if 'server_port' in self.config:
            self.app = Flask(self.id)
            self.setup_routes()
            port = self.config['server_port']
            threading.Thread(
                target=lambda: self.app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)).start()
        else:
            print("Error Starting the HTTP Server ! Check the configuration ...")

    def stop(self):
        print(f'Stopping protocol: {self.id} Type: {self.type}')
        pass

    def validate_config(self):
        required_keys = ["server_port"]
        if not validate_dict_keys(self.config, required_keys):
            raise InvalidConfigurationError(required_keys)

    def publish_sensor_telemetry_data(self, device_id, sensor_id, payload):
        pass

    def publish_device_telemetry_data(self, device_id, payload):
        pass

    def setup_routes(self):
        @self.app.route('/devices',
                        methods=['GET'],
                        endpoint='devices')
        def get_active_devices():
            result = []
            for device in self.device_dict.values():
                result.append(device.get_device_descr())
            return jsonify(result)

        @self.app.route('/devices/<device_id>',
                        methods=['GET'],
                        endpoint='device')
        def get_active_device(device_id):
            return jsonify(self.device_dict[device_id].get_device_descr())

        @self.app.route('/devices/<device_id>/sensors',
                        methods=['GET'],
                        endpoint='device_sensors')
        def get_sensors(device_id):
            result = [sensor.to_dict() for sensor in self.device_dict[device_id].sensors]
            return jsonify(result)

        @self.app.route('/devices/<device_id>/sensors/<sensor_id>',
                        methods=['GET'],
                        endpoint='device_sensor')
        def get_sensor(device_id, sensor_id):
            sensor = self.device_dict[device_id].get_sensor_by_id(sensor_id)
            if sensor:
                return jsonify(sensor.to_dict())
            else:
                abort(404, description=f"Sensor {sensor_id} not found")

        @self.app.route('/devices/<device_id>/actuators',
                        methods=['GET'],
                        endpoint='device_actuators')
        def list_actuators(device_id):
            result = [actuator.to_dict() for actuator in self.device_dict[device_id].actuators]
            return jsonify(result)

        @self.app.route('/devices/<device_id>/actuators/<actuator_id>',
                        methods=['GET'],
                        endpoint='device_actuator_read')
        def get_actuator(device_id, actuator_id):
            actuator = self.device_dict[device_id].get_actuator_by_id(actuator_id)
            if actuator:
                return jsonify(actuator.to_dict())
            else:
                abort(404, description=f"Actuator {actuator_id} not found")

        @self.app.route('/devices/<device_id>/actuators/<actuator_id>',
                        methods=['POST'],
                        endpoint='device_actuation_post')
        def control_actuator_post(device_id, actuator_id):
            action_payload = request.json if request.data else None
            action_type = "POST"
            if self.device_dict[device_id].get_actuator_by_id(actuator_id).handle_action(action_type, action_payload):
                return '', 204
            else:
                abort(404, description=f"Actuator {actuator_id} not found")

        @self.app.route('/devices/<device_id>/actuators/<actuator_id>',
                        methods=['PUT'],
                        endpoint='device_actuation_put')
        def control_actuator_put(device_id, actuator_id):
            action_payload = request.json if request.data else None
            action_type = "PUT"
            if self.device_dict[device_id].get_actuator_by_id(actuator_id).handle_action(action_type, action_payload):
                return '', 204
            else:
                abort(404, description=f"Actuator {actuator_id} not found")
