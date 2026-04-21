"""Tests for shared agent runtime helper utilities."""

from unittest.mock import Mock

from base_agent.utils.agent_runtime import (
    initialize_agent_runtime,
    run_agent_loop,
    send_result_with_monitor,
    shutdown_agent_runtime,
)


def test_initialize_agent_runtime_sets_up_components() -> None:
    """Runtime initialization should connect infrastructure and return components."""
    config_manager = Mock()
    config_manager.get_config.return_value = {"rabbitmq": {"host": "localhost"}}
    config_manager_factory = Mock(return_value=config_manager)

    performance_monitor = Mock()
    performance_monitor_factory = Mock(return_value=performance_monitor)

    comm = Mock()
    connect_factory = Mock(return_value=comm)
    logger = Mock()

    runtime = initialize_agent_runtime(
        agent_name="MATLAB",
        agent_id="agent-1",
        config_path="config.yaml",
        broker_type="rabbitmq",
        config_manager_factory=config_manager_factory,
        performance_monitor_factory=performance_monitor_factory,
        connect_factory=connect_factory,
        logger=logger,
    )

    config_manager_factory.assert_called_once_with("config.yaml")
    performance_monitor_factory.assert_called_once_with(
        config={"rabbitmq": {"host": "localhost"}}
    )
    connect_factory.assert_called_once_with(
        "agent-1",
        {"rabbitmq": {"host": "localhost"}},
        "rabbitmq",
    )
    comm.connect.assert_called_once_with()
    comm.setup.assert_called_once_with()
    comm.register_message_handler.assert_called_once_with()

    assert runtime.config_manager is config_manager
    assert runtime.config == {"rabbitmq": {"host": "localhost"}}
    assert runtime.performance_monitor is performance_monitor
    assert runtime.comm is comm


def test_run_agent_loop_handles_keyboard_interrupt() -> None:
    """KeyboardInterrupt should trigger graceful shutdown callback."""
    comm = Mock()
    comm.start_consuming.side_effect = KeyboardInterrupt
    logger = Mock()
    stop_func = Mock()

    run_agent_loop(
        agent_name="MATLAB",
        comm=comm,
        logger=logger,
        stop_func=stop_func,
    )

    stop_func.assert_called_once_with()
    logger.info.assert_any_call("Stopping MATLAB agent due to keyboard interrupt")


def test_run_agent_loop_handles_unexpected_exception() -> None:
    """Unexpected errors should be logged with traceback before stopping."""
    comm = Mock()
    processing_error = RuntimeError("boom")
    comm.start_consuming.side_effect = processing_error
    logger = Mock()
    stop_func = Mock()

    run_agent_loop(
        agent_name="MATLAB",
        comm=comm,
        logger=logger,
        stop_func=stop_func,
    )

    stop_func.assert_called_once_with()
    logger.error.assert_called_once_with(
        "Unexpected error while consuming messages: %s",
        processing_error,
    )
    logger.exception.assert_called_once_with("Stack trace:")


def test_shutdown_agent_runtime_logs_summary() -> None:
    """Shutdown helper should close comm and log summary metrics when available."""
    comm = Mock()
    performance_monitor = Mock()
    performance_monitor.get_summary.return_value = {"avg_total_time": 3.456}
    logger = Mock()

    shutdown_agent_runtime(
        agent_name="MATLAB",
        comm=comm,
        performance_monitor=performance_monitor,
        logger=logger,
    )

    comm.close.assert_called_once_with()
    logger.info.assert_any_call("Stopping MATLAB agent")
    logger.info.assert_any_call("Performance Summary:")
    logger.info.assert_any_call("  %s: %.2f", "avg_total_time", 3.456)


def test_send_result_with_monitor_records_only_on_success() -> None:
    """Performance monitor should be updated only for successful sends."""
    comm = Mock()
    performance_monitor = Mock()
    payload = {"status": "completed"}

    comm.send_result.return_value = True
    assert send_result_with_monitor(comm, performance_monitor, "dest", payload) is True
    performance_monitor.record_result_sent.assert_called_once_with()

    comm.send_result.return_value = False
    performance_monitor.record_result_sent.reset_mock()
    assert send_result_with_monitor(comm, performance_monitor, "dest", payload) is False
    performance_monitor.record_result_sent.assert_not_called()
