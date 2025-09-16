from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.protocol.protocol import Protocol

import threading
import time
import json


class IoTDevice(threading.Thread):
    def __init__(self,
                 device_id,
                 sensors,
                 actuators,
                 protocol: Protocol,
                 independent_communication,
                 device_update_delay_ms):
        super().__init__()

        self.id = device_id
        self.sensors = sensors
        self.actuators = actuators
        self.protocol = protocol
        self.independent_communication = independent_communication
        self.device_update_delay_ms = device_update_delay_ms
        self._stop_event = threading.Event()

        # Add device reference to the protocol
        self.protocol.device_dict[self.id] = self

    def update_all_sensors(self):
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
                    sensor.update_value()
                    data = sensor.to_dict()
                    self.protocol.publish_sensor_telemetry_data(self.id, sensor.id, json.dumps(data))
        else:
            sensor_data = self.update_all_sensors()
            if sensor_data:
                self.protocol.publish_device_telemetry_data(self.id, json.dumps(sensor_data))

    def run(self):
        print(f'Starting device: {self.id} ....')
        while not self._stop_event.is_set():
            self.communicate()
            if not self.independent_communication:
                time.sleep(self.device_update_delay_ms/1000)
            else:
                time.sleep(0.001)  # Short delay for continuous checking

    def stop(self):
        self._stop_event.set()

    def get_device_descr(self):
        return {
            "id": self.id,
            "sensors": [sensor.to_dict() for sensor in self.sensors],
            "actuators": [actuator.to_dict() for actuator in self.actuators],
            "device_update_delay": self.device_update_delay_ms
        }

    def get_sensor_by_id(self, sensor_id):
        for sensor in self.sensors:
            if sensor.id == sensor_id:
                return sensor
        return None

    def get_actuator_by_id(self, actuator_id):
        for actuator in self.actuators:
            if actuator.id == actuator_id:
                return actuator
        return None