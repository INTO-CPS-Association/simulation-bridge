import random
import csv
import string
import time
from app.utils.emulator_utils import SensorType


class CSVReader:
    """
    Reads data from a CSV file and provides methods to fetch values from specified columns.

    Attributes:
        csv_file (str): Path to the CSV file to be read.
        value_columns (list): List of column names from which values are to be extracted.
        timestamp_column (str or None): Optional. Column name containing timestamps (default: None).
        timestamp_unit (str): Unit of timestamps ('millisec' by default).

    Methods:
        __init__(csv_file, value_columns, timestamp_column=None, timestamp_unit='millisec'):
            Initializes the CSVReader with the given parameters and loads data from the CSV file.

        get_next_values():
            Fetches the next set of values from the CSV file as a dictionary based on value_columns.

        reset():
            Resets the current index to the beginning of the data.
    """

    def __init__(self, csv_file, value_columns, timestamp_column=None, timestamp_unit='millisec'):
        """
        Initializes the CSVReader instance.

        :param csv_file: Path to the CSV file to read.
        :param value_columns: List of column names to fetch values from.
        :param timestamp_column: Optional. Name of the column containing timestamps (default: None).
        :param timestamp_unit: Unit of timestamps (default: 'millisec').
        """
        self.csv_file = csv_file
        self.value_columns = value_columns
        self.timestamp_column = timestamp_column
        self.timestamp_unit = timestamp_unit
        self.data = []
        self.current_index = 0
        self._load_data()

    def _load_data(self):
        """
        Loads data from the CSV file into self.data as a list of dictionaries.
        """
        with open(self.csv_file, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                self.data.append(row)

    def get_next_values(self):
        """
        Retrieves the next set of values from the CSV file.
        :return: Dictionary containing values from specified columns.
        """
        if self.current_index < len(self.data):
            row = self.data[self.current_index]
            self.current_index += 1
            values = {column: row[column] for column in self.value_columns}
            return values
        else:
            self.current_index = 0
            return self.get_next_values()

    def reset(self):
        """
        Resets the current index to the beginning of the data.
        """
        self.current_index = 0


class Sensor:
    """
    Represents a sensor device with various types and capabilities.

    Attributes:
        id (str or int): Identifier for the sensor.
        type (str): Type of the sensor (e.g., numeric, boolean, string).
        update_time_ms (int): Time interval in milliseconds between sensor updates.
        initial_value (optional): Initial value of the sensor (default: None).
        min_val (optional): Minimum value for numeric sensors (default: None).
        max_val (optional): Maximum value for numeric sensors (default: None).
        csv_file (str or None): Path to a CSV file for simulated sensor data (default: None).
        value_columns (list or None): List of columns to read from the CSV file (default: None).
        use_csv_timestamp (bool): Whether to use timestamps from CSV (default: False).
        timestamp_column (str or None): Column name for timestamps in CSV (default: None).
        value_len (int or None): Length of generated random string (default: None).
        value (str or None): Fixed value for sensors with a fixed string type (default: None).
        timestamp_unit (str): Unit of timestamps ('millisec' by default).

    Methods:
        __init__(id, type, update_time_ms, initial_value=None, min_val=None, max_val=None,
                 csv_file=None, value_columns=None, use_csv_timestamp=False, timestamp_column=None,
                 value_len=None, value=None, timestamp_unit='millisec'):
            Initializes a new Sensor instance with specified attributes.

        generate_random_string(length):
            Generates a random string of specified length.

        generate_string():
            Generates a random string of length 10.

        current_value():
            Retrieves the current value of the sensor.

        update_value():
            Updates the sensor value based on configured rules or CSV data.

        should_update():
            Checks if the sensor should update its value based on update_time_ms.

        to_dict():
            Converts the Sensor instance to a dictionary representation.
    """

    def __init__(self,
                 id,
                 type,
                 update_time_ms,
                 initial_value=None,
                 min_val=None,
                 max_val=None,
                 csv_file=None,
                 value_columns=None,
                 use_csv_timestamp=False,
                 timestamp_column=None,
                 value_len=None,
                 value=None,
                 timestamp_unit='millisec'):
        """
        Initializes a new Sensor instance.

        :param id: Identifier for the sensor.
        :param type: Type of the sensor (numeric, boolean, fixed string, random string).
        :param update_time_ms: Time interval in milliseconds between sensor updates.
        :param initial_value: Optional. Initial value of the sensor.
        :param min_val: Optional. Minimum value for numeric sensors.
        :param max_val: Optional. Maximum value for numeric sensors.
        :param csv_file: Optional. Path to CSV file for simulated sensor data.
        :param value_columns: Optional. List of columns to read from CSV file.
        :param use_csv_timestamp: Optional. Whether to use timestamps from CSV (default: False).
        :param timestamp_column: Optional. Column name for timestamps in CSV.
        :param value_len: Optional. Length of generated random string.
        :param value: Optional. Fixed value for sensors with fixed string type.
        :param timestamp_unit: Optional. Unit of timestamps (default: 'millisec').
        """

        self.id = id
        self.type = type
        self.update_time_ms = update_time_ms
        self.min_val = min_val
        self.max_val = max_val
        self.csv_file = csv_file
        self.value_columns = value_columns
        self.use_csv_timestamp = use_csv_timestamp
        self.timestamp_column = timestamp_column
        self.timestamp_unit = timestamp_unit
        self.last_update_time = time.time() * 1000  # Convert to milliseconds
        self.last_value = initial_value
        self.csv_reader = None
        self.value = value
        self.value_len = value_len
        if csv_file and value_columns:
            self.csv_reader = CSVReader(csv_file, value_columns, timestamp_column, timestamp_unit)

    def generate_random_string(self, length):
        """
        Generate a random string of fixed length.

        :param length: The length of the random string.
        :type length: int
        :return: A random string of the specified length.
        :rtype: str
        """
        characters = string.ascii_letters + string.digits
        random_string = ''.join(random.choice(characters) for _ in range(length))
        return random_string

    def generate_string(self):
        """
        Generates a random string of length 10.

        :return: A random string of length 10.
        :rtype: str
        """
        return self.generate_random_string(10)

    def current_value(self):
        """
        Retrieves the current value of the sensor.

        :return: Current value of the sensor.
        """
        return self.last_value

    def update_value(self):
        """
        Updates the sensor value based on configured rules or CSV data.

        :return: Updated sensor value.
        """
        if self.csv_reader:
            value = self.csv_reader.get_next_values()
            if self.type == SensorType.SENSOR_NUMERIC_TYPE.value:
                if not isinstance(value, dict):
                    self.last_value = float(value)
                else:
                    for key in value:
                        try:
                            value[key] = float(value[key])
                        except ValueError as e:
                            print(f"Error converting {key}: {value[key]} to float. {e}")
                    self.last_value = value
            elif self.type == SensorType.SENSOR_BOOLEAN_TYPE.value:
                if not isinstance(value, dict):
                    self.last_value = value.lower() in ['true', '1']
                else:
                    for key in value:
                        try:
                            value[key] = value[key].lower() in ['true', '1']
                        except ValueError as e:
                            print(f"Error converting {key}: {value[key]} to float. {e}")
                    self.last_value = value
            elif self.type == SensorType.SENSOR_STRING_TYPE.value:
                self.last_value = value
        else:
            if self.type == SensorType.SENSOR_NUMERIC_TYPE.value and self.min_val is not None and self.max_val is not None:
                self.last_value = random.uniform(self.min_val, self.max_val)
            elif self.type == SensorType.SENSOR_BOOLEAN_TYPE.value:
                self.last_value = random.choice([True, False])
            elif self.type == SensorType.SENSOR_FIXED_STRING_TYPE.value and self.value is not None:
                self.last_value = self.value
            elif self.type == SensorType.SENSOR_RANDOM_STRING_TYPE.value and self.value_len is not None:
                self.last_value = self.generate_string()
            else:
                self.last_value = None
        return self.last_value

    def should_update(self):
        """
        Checks if the sensor should update its value based on the configured update interval.

        This method compares the current time with the last update time of the sensor. If the time elapsed
        since the last update exceeds the configured update interval, it updates the last update time and
        returns True. Otherwise, it returns False indicating that the sensor should not update yet.

        :return: True if the sensor should update, False otherwise.
        :rtype: bool
        """
        current_time = time.time() * 1000  # Convert to milliseconds
        if current_time - self.last_update_time >= self.update_time_ms:
            self.last_update_time = current_time
            return True
        return False

    def to_dict(self):
        """
        Converts the Sensor instance to a dictionary representation.

        :return: A dictionary containing the sensor's id, current value, and last update time.
        :rtype: dict
        """
        return {
            "id": self.id,
            "value": self.last_value,
            "last_update_time_ms": int(self.last_update_time)
        }