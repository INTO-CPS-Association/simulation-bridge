import yaml
import random
import threading
import paho.mqtt.client as mqtt
import requests
from flask import Flask, jsonify, request, abort
import csv
import time

class CSVReader:
    def __init__(self, csv_file, value_column, timestamp_column=None, timestamp_unit='millisec'):
        self.csv_file = csv_file
        self.value_column = value_column
        self.timestamp_column = timestamp_column
        self.timestamp_unit = timestamp_unit
        self.data = []
        self.current_index = 0
        self._load_data()

    def _load_data(self):
        with open(self.csv_file, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                self.data.append(row)

    def get_next_value(self):
        if self.current_index < len(self.data):
            row = self.data[self.current_index]
            self.current_index += 1
            value = row[self.value_column]
            timestamp = None
            if self.timestamp_column:
                timestamp = row[self.timestamp_column]
                if self.timestamp_unit == 'second':
                    timestamp = int(timestamp)
                elif self.timestamp_unit == 'millisec':
                    timestamp = int(timestamp) / 1000
                elif self.timestamp_unit == 'nanosec':
                    timestamp = int(timestamp) / 1_000_000_000
            return value, timestamp
        else:
            self.current_index = 0
            return self.get_next_value()

    def reset(self):
        self.current_index = 0

class Sensor:
    def __init__(self, id, type, unit, update_time_ms, min_val=None, max_val=None, csv_file=None, value_column=None, use_csv_timestamp=False, timestamp_column=None, timestamp_unit='millisec'):
        self.id = id
        self.type = type
        self.unit = unit
        self.update_time_ms = update_time_ms
        self.min_val = min_val
        self.max_val = max_val
        self.csv_file = csv_file
        self.value_column = value_column
        self.use_csv_timestamp = use_csv_timestamp
        self.timestamp_column = timestamp_column
        self.timestamp_unit = timestamp_unit
        self.last_update_time = time.time() * 1000  # Convert to milliseconds
        self.last_value = None
        self.csv_reader = None
        if csv_file and value_column:
            self.csv_reader = CSVReader(csv_file, value_column, timestamp_column, timestamp_unit)

    def generate_value(self):
        if self.csv_reader:
            value, timestamp = self.csv_reader.get_next_value()
            if timestamp and self.use_csv_timestamp:
                current_time = time.time() * 1000  # Convert to milliseconds
                self.update_time_ms = (timestamp * 1000) - (current_time - self.last_update_time)
            if self.type == 'numeric':
                self.last_value = float(value)
            elif self.type == 'boolean':
                self.last_value = value.lower() in ['true', '1']
            elif self.type == 'string':
                self.last_value = value
        else:
            if self.type == 'numeric' and self.min_val is not None and self.max_val is not None:
                self.last_value = random.uniform(self.min_val, self.max_val)
            elif self.type == 'boolean':
                self.last_value = random.choice([True, False])
            elif self.type == 'string':
                self.last_value = "example_string"
            else:
                self.last_value = None
        return self.last_value

    def should_update(self):
        current_time = time.time() * 1000  # Convert to milliseconds
        if current_time - self.last_update_time >= self.update_time_ms:
            self.last_update_time = current_time
            return True
        return False


class Actuator:
    def __init__(self, id, type, unit):
        self.id = id
        self.type = type
        self.unit = unit


class Protocol:
    def __init__(self, type, **kwargs):
        self.type = type
        self.config = kwargs

    def send_data(self, data):
        if self.type == 'mqtt':
            client = mqtt.Client()
            client.connect(self.config['broker'], self.config['port'])
            client.publish(self.config['topic'], data)
            client.disconnect()
        elif self.type == 'http':
            requests.post(self.config['url'], json=data)

    def read_data(self):
        if self.type == 'http' and 'read_url' in self.config:
            response = requests.get(self.config['read_url'])
            if response.status_code == 200:
                return response.json()
            else:
                return None
        else:
            return None


class IoTDevice(threading.Thread):
    def __init__(self, device_id, sensors, actuators, protocol, independent_communication, device_update_delay):
        super().__init__()
        self.id = device_id
        self.sensors = sensors
        self.actuators = actuators
        self.protocol = protocol
        self.independent_communication = independent_communication
        self.device_update_delay = device_update_delay
        self._stop_event = threading.Event()
        self.app = Flask(device_id)
        self.setup_routes()

    def read_sensors(self):
        sensor_data = {}
        for sensor in self.sensors:
            if sensor.should_update():
                sensor_data[sensor.id] = sensor.update_value()
            else:
                sensor_data[sensor.id] = sensor.last_value
        return sensor_data

    def read_sensor(self, sensor_id):
        for sensor in self.sensors:
            if sensor.id == sensor_id:
                if sensor.should_update():
                    return {sensor.id: sensor.update_value()}
                else:
                    return {sensor.id: sensor.last_value}
        return None

    def operate_actuator(self, actuator_id, command):
        for actuator in self.actuators:
            if actuator.id == actuator_id:
                print(f"Operating actuator {actuator.id} with command {command}")
                return True
        return False

    def get_actuators(self):
        actuator_list = {actuator.id: {"type": actuator.type, "unit": actuator.unit} for actuator in self.actuators}
        return actuator_list

    def communicate(self):
        if self.independent_communication:
            for sensor in self.sensors:
                if sensor.should_update():
                    data = {sensor.id: sensor.update_value()}
                    self.protocol.publish_sensor_telemetry_data(data)
                    print(f"Sent data: {data}")
        else:
            sensor_data = self.read_sensors()
            if sensor_data:
                self.protocol.publish_sensor_telemetry_data(sensor_data)
                print(f"Sent data: {sensor_data}")

    def setup_routes(self):
        @self.app.route('/sensors', methods=['GET'])
        def get_sensors():
            sensor_data = self.read_sensors()
            return jsonify(sensor_data)

        @self.app.route('/sensors/<sensor_id>', methods=['GET'])
        def get_sensor(sensor_id):
            sensor_data = self.read_sensor(sensor_id)
            if sensor_data:
                return jsonify(sensor_data)
            else:
                abort(404, description=f"Sensor {sensor_id} not found")

        @self.app.route('/actuators', methods=['GET'])
        def list_actuators():
            actuator_list = self.get_actuators()
            return jsonify(actuator_list)

        @self.app.route('/actuators/<actuator_id>', methods=['POST'])
        def control_actuator(actuator_id):
            command = request.json
            if self.operate_actuator(actuator_id, command):
                return '', 204
            else:
                abort(404, description=f"Actuator {actuator_id} not found")

    def run(self):
        if self.protocol.type == 'http' and 'server_port' in self.protocol.config:
            port = self.protocol.config['server_port']
            self.app.run(host='0.0.0.0', port=port, use_reloader=False)
        else:
            while not self._stop_event.is_set():
                self.communicate()
                if not self.independent_communication:
                    time.sleep(self.device_update_delay)
                else:
                    time.sleep(1)  # Short delay for continuous checking

    def stop(self):
        self._stop_event.set()


def load_devices_from_yaml(yaml_file):
    with open(yaml_file, 'r') as file:
        config = yaml.safe_load(file)

    devices = []
    for device_config in config['devices']:
        sensors = [Sensor(**sensor) for sensor in device_config['sensors']]
        actuators = [Actuator(**actuator) for actuator in device_config['actuators']]
        protocol = Protocol(**device_config['protocol'])
        independent_communication = device_config.get('independent_communication', False)
        device_update_delay = device_config.get('device_update_delay', 10000)  # in milliseconds
        device = IoTDevice(device_config['id'], sensors, actuators, protocol, independent_communication,
                           device_update_delay)
        devices.append(device)

    return devices


if __name__ == "__main__":
    devices = load_devices_from_yaml('../conf/config.yaml')
    for device in devices:
        device.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for device in devices:
            device.stop()
        for device in devices:
            device.join()

