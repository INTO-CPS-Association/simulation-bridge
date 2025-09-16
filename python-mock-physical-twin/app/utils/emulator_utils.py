from enum import Enum


class SensorType(Enum):
    """
   Enumeration defining types of sensors.

   Attributes:
       SENSOR_NUMERIC_TYPE (str): Numeric sensor type.
       SENSOR_BOOLEAN_TYPE (str): Boolean sensor type.
       SENSOR_STRING_TYPE (str): String sensor type.
       SENSOR_RANDOM_STRING_TYPE (str): Random string sensor type.
       SENSOR_FIXED_STRING_TYPE (str): Fixed string sensor type.
   """
    SENSOR_NUMERIC_TYPE = "numeric"
    SENSOR_BOOLEAN_TYPE = "boolean"
    SENSOR_STRING_TYPE = "string"
    SENSOR_RANDOM_STRING_TYPE = "random_string"
    SENSOR_FIXED_STRING_TYPE = "fixed_string"


class ActuatorType(Enum):
    """
    Enumeration defining types of actuators.

    Attributes:
        ACTUATOR_NUMERIC_TYPE (str): Numeric actuator type.
        ACTUATOR_BOOLEAN_TYPE (str): Boolean actuator type.
        ACTUATOR_STRING_TYPE (str): String actuator type.
    """
    ACTUATOR_NUMERIC_TYPE = "numeric"
    ACTUATOR_BOOLEAN_TYPE = "boolean"
    ACTUATOR_STRING_TYPE = "string"


class ProtocolType(Enum):
    """
    Enumeration defining types of communication protocols.

    Attributes:
        HTTP_PROTOCOL_TYPE (str): HTTP protocol type.
        MQTT_PROTOCOL_TYPE (str): MQTT protocol type.
    """
    HTTP_PROTOCOL_TYPE = "http"
    MQTT_PROTOCOL_TYPE = "mqtt"


class TimeUnit(Enum):
    """
    Enumeration defining units of time.

    Attributes:
        SECONDS_TIME_UNIT (str): Seconds time unit.
        MILLI_SECONDS_TIME_UNIT (str): Milliseconds time unit.
        NANO_SECONDS_TIME_UNIT (str): Nanoseconds time unit.
    """
    SECONDS_TIME_UNIT = "sec"
    MILLI_SECONDS_TIME_UNIT = "msec"
    NANO_SECONDS_TIME_UNIT = "nsec"