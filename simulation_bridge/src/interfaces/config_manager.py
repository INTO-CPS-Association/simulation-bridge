from typing import Optional, Dict, Any


class IConfigManager:
    """
    Interface for the Configuration Manager that handles YAML-based configuration
    for the application, including validation and default fallback.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Initialize the configuration manager.

        Args:
            config_path (Optional[str]): Path to the configuration file.
                                         If not specified, defaults to the standard location.
        """
        pass

    def _validate_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the loaded configuration data using a Pydantic model.

        Args:
            config_data (Dict[str, Any]): Raw configuration data.

        Returns:
            Dict[str, Any]: Validated configuration dictionary.

        Raises:
            ValidationError: If validation fails.
        """
        pass

    def get_default_config(self) -> Dict[str, Any]:
        """
        Get the default configuration values.

        Returns:
            Dict[str, Any]: Default configuration parameters.
        """
        pass

    def get_config(self) -> Dict[str, Any]:
        """
        Retrieve the loaded configuration.

        Returns:
            Dict[str, Any]: Current configuration parameters.
        """
        pass

    def get_rabbitmq_config(self) -> Dict[str, Any]:
        """
        Retrieve the RabbitMQ-specific configuration.

        Returns:
            Dict[str, Any]: RabbitMQ connection parameters.
        """
        pass

    def get_infrastructure_config(self) -> Dict[str, Any]:
        """
        Retrieve the infrastructure-specific configuration (exchanges, queues, bindings).

        Returns:
            Dict[str, Any]: Infrastructure configuration details.
        """
        pass
