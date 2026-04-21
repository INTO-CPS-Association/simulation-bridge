"""
MatlabAgent implementation - An implementation of the MatlabAgent class using the Connect
abstraction to manage communication and handle simulation processing.
"""

from typing import Any, Dict, Optional

import pika
import yaml
from base_agent.comm.connect import Connect
from base_agent.comm.rabbitmq.rabbitmq_manager import RabbitMQManager
from base_agent.interfaces.config_manager import IConfigManager
from base_agent.utils.logger import get_logger
from base_agent.utils.agent_runtime import (
    initialize_agent_runtime,
    run_agent_loop,
    send_result_with_monitor,
    shutdown_agent_runtime,
)

from ..comm.rabbitmq.message_handler import MessageHandler
from ..utils.config_manager import ConfigManager
from ..utils.performance_monitor import PerformanceMonitor

# Configure logger
logger = get_logger("MATLAB-AGENT")


class MatlabAgent:
    """
    An agent that interfaces with a MATLAB simulation through a communication layer.
    This component handles message reception, processing, and result distribution
    while remaining decoupled from the specific messaging technology.
    """

    def __init__(
            self,
            agent_id: str,
            config_path: Optional[str] = None,
            broker_type: str = "rabbitmq") -> None:
        """
        Initialize the MATLAB agent.

        Args:
            agent_id (str): The ID of the agent
            config_path (Optional[str]): Path to the configuration file (optional)
            broker_type (str): The type of message broker to use (default: "rabbitmq")
        """
        self.agent_id: str = agent_id

        def broker_factory(
            current_agent_id: str,
            current_config: Dict[str, Any],
        ) -> RabbitMQManager:
            return RabbitMQManager(
                agent_id=current_agent_id,
                config=current_config,
                logger=logger,
                pika_module=pika,
                yaml_module=yaml,
            )

        def connect_factory(
            current_agent_id: str,
            current_config: Dict[str, Any],
            current_broker_type: str,
        ) -> Connect:
            return Connect(
                agent_id=current_agent_id,
                config=current_config,
                broker_type=current_broker_type,
                broker_factory=broker_factory,
                message_handler_factory=MessageHandler,
                logger=logger,
            )

        try:
            runtime = initialize_agent_runtime(
                agent_name="MATLAB",
                agent_id=self.agent_id,
                config_path=config_path,
                broker_type=broker_type,
                config_manager_factory=ConfigManager,
                performance_monitor_factory=PerformanceMonitor,
                connect_factory=connect_factory,
                logger=logger,
            )
        except ConnectionError as error:
            logger.error("Connection error while initializing MATLAB agent: %s", error)
            raise
        self.config_manager: IConfigManager = runtime.config_manager
        self.config: Dict[str, Any] = runtime.config
        self.performance_monitor = runtime.performance_monitor
        self.comm = runtime.comm

    def start(self) -> None:
        """
        Start the agent and begin consuming messages.
        """
        run_agent_loop(
            agent_name="MATLAB",
            comm=self.comm,
            logger=logger,
            stop_func=self.stop,
        )

    def stop(self) -> None:
        """
        Stop the agent and close all connections.
        """
        shutdown_agent_runtime(
            agent_name="MATLAB",
            comm=self.comm,
            performance_monitor=self.performance_monitor,
            logger=logger,
        )

    def send_result(self, destination: str, result: Dict[str, Any]) -> bool:
        """
        Send operation results to the specified destination.

        Args:
            destination (str): The destination identifier
            result (Dict[str, Any]): The result data to be sent

        Returns:
            bool: True if successful, False otherwise
        """
        return send_result_with_monitor(
            comm=self.comm,
            performance_monitor=self.performance_monitor,
            destination=destination,
            result=result,
        )
