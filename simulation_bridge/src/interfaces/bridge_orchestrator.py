from typing import Any, Dict, Optional


class IBridgeOrchestrator:
    """
    Interface for the Bridge Orchestrator class responsible for managing communication
    between Digital Twins (DTs), Physical Twins (PTs), Mock Physical Twins (MockPTs),
    and simulators via RabbitMQ.
    """

    def __init__(self, simulation_bridge_id: str,
                 config_path: Optional[str] = None) -> None:
        """
        Initialize the Bridge Orchestrator with the specified configuration.

        Args:
            simulation_bridge_id (str): Unique identifier for the bridge instance.
            config_path (Optional[str]): Path to the configuration file.
        """
        pass

    def _create_rabbitmq_connection(self) -> Any:
        """
        Create a RabbitMQ connection based on the loaded configuration.

        Returns:
            Any: Configured RabbitMQ connection object.
        """
        pass

    def setup_infrastructure(self) -> None:
        """
        Set up the RabbitMQ infrastructure, including exchanges, queues, and bindings.
        """
        pass

    def start(self) -> None:
        """
        Start the bridge orchestrator, initializing message consumption from queues.
        """
        pass

    def stop(self) -> None:
        """
        Stop the bridge orchestrator, stopping message consumption and closing connections.
        """
        pass
