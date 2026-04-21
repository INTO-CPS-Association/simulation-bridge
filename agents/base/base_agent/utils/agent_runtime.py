"""Shared lifecycle helpers for simulator agent runtime classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol

from base_agent.interfaces.config_manager import IConfigManager


class AgentComm(Protocol):
    """Protocol for communication backends used by runtime helpers."""

    def connect(self) -> None:
        """Open the communication backend connection."""

    def setup(self) -> None:
        """Set up communication backend resources."""

    def register_message_handler(self) -> None:
        """Register the default message handler callback."""

    def start_consuming(self) -> None:
        """Begin consuming incoming simulation messages."""

    def close(self) -> None:
        """Close active communication resources."""

    def send_result(self, destination: str, result: Dict[str, Any]) -> bool:
        """Publish a simulation result to the given destination."""


class AgentPerformanceMonitor(Protocol):
    """Protocol for performance monitor methods used by runtime helpers."""

    def get_summary(self) -> Dict[str, float]:
        """Return aggregated performance metrics for completed operations."""

    def record_result_sent(self) -> None:
        """Record that a result payload was successfully sent."""


@dataclass
class AgentRuntimeComponents:
    """Container for initialized runtime components."""

    config_manager: IConfigManager
    config: Dict[str, Any]
    performance_monitor: AgentPerformanceMonitor
    comm: AgentComm


def initialize_agent_runtime(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    agent_name: str,
    agent_id: str,
    config_path: Optional[str],
    broker_type: str,
    config_manager_factory: Callable[[Optional[str]], IConfigManager],
    performance_monitor_factory: Callable[..., AgentPerformanceMonitor],
    connect_factory: Callable[[str, Dict[str, Any], str], AgentComm],
    logger: Any,
) -> AgentRuntimeComponents:
    """Build and connect shared runtime components for an agent implementation."""
    logger.info("Initializing %s agent with ID: %s", agent_name, agent_id)

    config_manager = config_manager_factory(config_path)
    config = config_manager.get_config()
    performance_monitor = performance_monitor_factory(config=config)

    comm = connect_factory(agent_id, config, broker_type)
    comm.connect()
    comm.setup()
    comm.register_message_handler()

    logger.debug("%s agent initialized successfully", agent_name)
    return AgentRuntimeComponents(
        config_manager=config_manager,
        config=config,
        performance_monitor=performance_monitor,
        comm=comm,
    )


def run_agent_loop(
    agent_name: str,
    comm: AgentComm,
    logger: Any,
    stop_func: Callable[[], None],
) -> None:
    """Start message consumption loop with standard error handling."""
    try:
        logger.info("%s agent running and listening for requests", agent_name)
        comm.start_consuming()
    except KeyboardInterrupt:
        logger.info(f"Stopping {agent_name} agent due to keyboard interrupt")
        stop_func()
    except ConnectionError as error:
        logger.error("Connection error while consuming messages: %s", error)
        stop_func()
    except TimeoutError as error:
        logger.error("Timeout error while consuming messages: %s", error)
        stop_func()
    except Exception as error:  # pylint: disable=broad-exception-caught
        logger.error("Unexpected error while consuming messages: %s", error)
        logger.exception("Stack trace:")
        stop_func()


def shutdown_agent_runtime(
    agent_name: str,
    comm: AgentComm,
    performance_monitor: AgentPerformanceMonitor,
    logger: Any,
) -> None:
    """Close communication resources and log performance summary."""
    logger.info(f"Stopping {agent_name} agent")
    comm.close()

    summary = performance_monitor.get_summary()
    if summary:
        logger.info("Performance Summary:")
        for metric, value in summary.items():
            logger.info("  %s: %.2f", metric, value)


def send_result_with_monitor(
    comm: AgentComm,
    performance_monitor: AgentPerformanceMonitor,
    destination: str,
    result: Dict[str, Any],
) -> bool:
    """Send a result payload and record metrics on success."""
    success = comm.send_result(destination, result)
    if success:
        performance_monitor.record_result_sent()
    return success


__all__ = [
    "AgentComm",
    "AgentPerformanceMonitor",
    "AgentRuntimeComponents",
    "initialize_agent_runtime",
    "run_agent_loop",
    "shutdown_agent_runtime",
    "send_result_with_monitor",
]
