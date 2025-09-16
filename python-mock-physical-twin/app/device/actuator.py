import time


class Actuator:
    """
    Represents an Actuator device that performs actions based on external requests.

    Attributes:
        id (str or int): Identifier for the actuator.
        type (str): Type of the actuator.
        current_value (optional): Current value or state of the actuator (default: None).
        last_update_time (float): Timestamp of the last update in milliseconds since epoch.

    Methods:
        __init__(id, type, initial_value=None):
            Initializes a new Actuator instance with given id, type, and optional initial value.

        handle_action(request_type, request_payload):
            Handles an action request on the actuator, prints the action details, and returns True.

        to_dict():
            Converts the Actuator instance to a dictionary containing its attributes.
    """

    def __init__(self, id, type, initial_value=None):
        """
        Initialize an Actuator object with an id, type, and optional initial_value.

        Args:
            id (str or int): Identifier for the actuator.
            type (str): Type of the actuator.
            initial_value (optional): Initial value of the actuator (default: None).
        """
        self.id = id
        self.type = type
        self.current_value = initial_value
        self.last_update_time = time.time() * 1000  # Convert to milliseconds

    def handle_action(self, request_type, request_payload):
        """
        Handle an action request on the actuator.

        Args:
            request_type (str): Type of the action request.
            request_payload (object): Payload or data associated with the action request.

        Returns:
            bool: True if the action was successfully handled, False otherwise.
        """
        print(f'Actuator {self.id} handling Action: {request_type} with Payload: {request_payload}')
        return True

    def to_dict(self):
        """
        Convert the Actuator object to a dictionary representation.

        Returns:
            dict: Dictionary containing id, type, current_value, and last_update_time of the Actuator.
        """
        return {
            "id": self.id,
            "type": self.type,
            "current_value": self.current_value,
            "last_update_time": self.last_update_time
        }