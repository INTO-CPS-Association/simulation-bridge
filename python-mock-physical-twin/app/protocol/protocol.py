from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.device.iot_device import IoTDevice
    from typing import Dict


class InvalidConfigurationError(Exception):
    """Exception raised for errors in the configuration.

    Attributes:
        missing_keys -- list of keys that are missing or have None values
        message -- explanation of the error
    """
    def __init__(self, required_keys, message="Invalid configuration: missing or null keys"):
        self.required_keys = required_keys
        self.message = f"{message}: {', Required keys:'.join(required_keys)}"
        super().__init__(self.message)


def validate_dict_keys(dictionary, keys):
    """
    Verify that the dictionary contains all the specified keys in the list
    and that the respective values are not null (None).

    :param dictionary: The dictionary to verify.
    :param keys: The list of keys that the dictionary must contain.
    :return: True if all keys are present and their respective values are not null, False otherwise.
    """
    for key in keys:
        if key not in dictionary or dictionary[key] is None:
            return False
    return True


class Protocol:
    """
    Abstract base class representing a communication protocol used by IoT devices.

    Attributes:
        id (str): The identifier for the protocol.
        type (str): The type of the protocol.
        device_dict (dict): A dictionary mapping device IDs to IoTDevice objects.
        config (dict): Configuration parameters specific to the protocol.

    Methods:
        __init__(protocol_id, protocol_type, device_dict=None, config=None):
            Initializes a Protocol instance with the given ID, type, optional device dictionary,
            and configuration parameters.

        start():
            Abstract method to be implemented by subclasses to start the protocol.

        stop():
            Abstract method to be implemented by subclasses to stop the protocol.

        validate_config():
            Abstract method to be implemented by subclasses to validate the protocol configuration.

        publish_sensor_telemetry_data(device_id, sensor_id, payload):
            Abstract method to be implemented by subclasses to publish sensor telemetry data.

        publish_device_telemetry_data(device_id, payload):
            Abstract method to be implemented by subclasses to publish device telemetry data.
    """

    def __init__(self,
                 protocol_id,
                 protocol_type,
                 device_dict: Dict[str, IoTDevice] = None,
                 config: Dict = None):
        """
        Initialize a Protocol instance.

        :param protocol_id: The identifier for the protocol.
        :type protocol_id: str
        :param protocol_type: The type of the protocol.
        :type protocol_type: str
        :param device_dict: A dictionary mapping device IDs to IoTDevice objects, defaults to None.
        :type device_dict: dict, optional
        :param config: Configuration parameters for the protocol, defaults to None.
        :type config: dict, optional
        """

        self.id = protocol_id
        self.type = protocol_type

        if device_dict is None:
            self.device_dict = {}
        else:
            self.device_dict = device_dict

        self.config = config

        self.validate_config()

    def start(self):
        """
        Start method to be implemented by subclasses.
        This method should be overridden by subclasses to define the start behavior of the protocol.
        """
        raise NotImplementedError("start method must be implemented by subclasses")

    def stop(self):
        """
       Stop method to be implemented by subclasses.
       This method should be overridden by subclasses to define the stop behavior of the protocol.
       """
        raise NotImplementedError("stop method must be implemented by subclasses")

    def validate_config(self):
        """
        Validate configuration method to be implemented by subclasses.
        This method should be overridden by subclasses to validate the protocol configuration.
        """
        raise NotImplementedError("validate_config method must be implemented by subclasses")

    def publish_sensor_telemetry_data(self, device_id, sensor_id, payload):
        """
        Publish telemetry data of a single sensor, method to be implemented by subclasses.

        This method should be overridden by subclasses to define how sensor telemetry data is published
        by the protocol.

        :param device_id: The ID of the device.
        :type device_id: str
        :param sensor_id: The ID of the sensor.
        :type sensor_id: str
        :param payload: The data payload to be published.
        """
        raise NotImplementedError("publish_sensor_telemetry_data method must be implemented by subclasses")

    def publish_device_telemetry_data(self, device_id, payload):
        """
        Publish telemetry data for the entire device with all its sensors, method to be implemented by subclasses.

        This method should be overridden by subclasses to define how device telemetry data is published
        by the protocol.

        :param device_id: The ID of the device.
        :type device_id: str
        :param payload: The data payload to be published.
        """
        raise NotImplementedError("publish_device_telemetry_data method must be implemented by subclasses")