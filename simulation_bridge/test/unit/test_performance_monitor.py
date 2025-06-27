"""
Test suite for PerformanceMonitor and PerformanceMetrics.
"""
from unittest.mock import patch, MagicMock, mock_open
import pytest

from simulation_bridge.src.utils.performance_monitor import PerformanceMonitor
from simulation_bridge.src.utils.performance_monitor import PerformanceMetrics

# pylint: disable=redefined-outer-name,protected-access,line-too-long,unused-argument

@pytest.fixture
def config_enabled(tmp_path):
    """Configuration with performance monitoring enabled."""
    log_file = tmp_path / "performance_logs" / "performance_metrics.csv"
    return {
        'performance': {
            'enabled': True,
            'file': str(log_file)
        }
    }


@pytest.fixture
def config_disabled():
    """Configuration with performance monitoring disabled."""
    return {'performance': {'enabled': False}}


@pytest.fixture
def monitor_enabled(config_enabled):
    """PerformanceMonitor instance with enabled config."""
    # Clear singleton for test isolation
    PerformanceMonitor._instance = None
    PerformanceMonitor._initialized = False
    monitor = PerformanceMonitor(config_enabled)
    yield monitor
    # Clean up singleton after test
    PerformanceMonitor._instance = None
    PerformanceMonitor._initialized = False


@pytest.fixture
def monitor_disabled(config_disabled):
    """PerformanceMonitor instance with disabled config."""
    PerformanceMonitor._instance = None
    PerformanceMonitor._initialized = False
    monitor = PerformanceMonitor(config_disabled)
    yield monitor
    PerformanceMonitor._instance = None
    PerformanceMonitor._initialized = False


def test_singleton_behavior(config_enabled):
    """Ensure PerformanceMonitor is a singleton."""
    PerformanceMonitor._instance = None
    PerformanceMonitor._initialized = False

    m1 = PerformanceMonitor(config_enabled)
    m2 = PerformanceMonitor(config_enabled)
    assert m1 is m2


def test_initialization_creates_dir_and_file(tmp_path, config_enabled):
    """Test directory creation and CSV header writing on init."""
    with patch("simulation_bridge.src.utils.performance_monitor.psutil.Process") as mock_process, \
            patch("builtins.open", mock_open()) as mock_file, \
            patch("pathlib.Path.mkdir") as mock_mkdir:

        mock_process.return_value = MagicMock()
        PerformanceMonitor._instance = None
        PerformanceMonitor._initialized = False

        monitor = PerformanceMonitor(config_enabled)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_file.assert_called_once_with(
            monitor.csv_path, 'w', newline='', encoding='utf-8')


def test_start_operation_creates_metric(monitor_enabled):
    """start_operation should create a new PerformanceMetrics entry."""
    op_id = "op1"
    monitor_enabled.start_operation(op_id)
    assert op_id in monitor_enabled.metrics_by_operation_id
    metric = monitor_enabled.metrics_by_operation_id[op_id]
    assert metric.operation_id == op_id
    assert metric.timestamp > 0


def test_record_timestamps_update_fields(monitor_enabled):
    """Recording timestamps updates the correct metric fields."""
    op_id = "op2"
    monitor_enabled.start_operation(op_id)

    with patch("time.time", return_value=1234.5):
        monitor_enabled.record_core_received_input(op_id)
        assert monitor_enabled.metrics_by_operation_id[op_id].core_received_input_time == 1234.5

        monitor_enabled.record_core_sent_input(op_id)
        assert monitor_enabled.metrics_by_operation_id[op_id].core_sent_input_time == 1234.5

        monitor_enabled.record_result_sent(op_id)
        assert monitor_enabled.metrics_by_operation_id[op_id].result_sent_time == 1234.5


def test_record_core_received_result_appends_time_and_updates_metrics(
        monitor_enabled):
    """record_core_received_result appends timestamp and updates system metrics."""
    op_id = "op3"
    monitor_enabled.start_operation(op_id)
    with patch("time.time", return_value=1000), \
            patch.object(monitor_enabled, "_update_system_metrics") as mock_update:
        monitor_enabled.record_core_received_result(op_id)
        metric = monitor_enabled.metrics_by_operation_id[op_id]
        assert metric.result_times[-1] == 1000
        mock_update.assert_called_once_with(metric)


def test_finalize_operation_calculates_metrics_and_saves(
        monitor_enabled, tmp_path):
    """finalize_operation computes overheads and calls save method."""
    op_id = "op4"
    monitor_enabled.start_operation(op_id)
    metric = monitor_enabled.metrics_by_operation_id[op_id]

    # Set timestamps for calculation - using non-zero values to avoid falsy
    # condition issues
    metric.request_received_time = 1.0
    metric.core_sent_input_time = 2.0
    metric.result_sent_time = 6.0
    metric.result_times = [3.0, 4.0, 5.0]

    with patch("time.time", return_value=10), \
            patch.object(monitor_enabled, "_save_metrics_to_csv") as mock_save, \
            patch.object(monitor_enabled, "_update_system_metrics") as mock_update:

        monitor_enabled.finalize_operation(op_id)

        # The metric should be removed after finalize
        assert op_id not in monitor_enabled.metrics_by_operation_id

        # Check calculations
        # time.time() - request_received_time = 10 - 1 = 9
        assert abs(metric.total_duration - 9.0) < 0.1
        # core_sent_input_time - request_received_time = 2 - 1 = 1
        assert abs(metric.input_overhead - 1.0) < 0.1
        # result_sent_time - last_result_time = 6 - 5 = 1
        assert abs(metric.output_overhead - 1.0) < 0.1
        # last_result_time - core_sent_input_time = 5 - 2 = 3
        assert abs(metric.processing_duration - 3.0) < 0.1
        # input_overhead + output_overhead = 1 + 1 = 2
        assert abs(metric.total_overhead - 2.0) < 0.1

        mock_save.assert_called_once_with(metric)
        mock_update.assert_called()


def test_save_metrics_to_csv_writes_file(monitor_enabled, tmp_path):
    """_save_metrics_to_csv appends correct CSV row."""
    op_id = "op5"
    metric = PerformanceMetrics(
        operation_id=op_id,
        timestamp=1,
        request_received_time=1,
        core_received_input_time=1,
        core_sent_input_time=1,
        result_times=[1, 2, 3],
        result_sent_time=4,
        cpu_percent=10,
        memory_rss_mb=50,
        total_duration=5,
        input_overhead=1,
        output_overhead=1,
        total_overhead=2,
        processing_duration=2
    )
    monitor_enabled.metrics_history = []

    with patch("builtins.open", mock_open()) as mock_file, \
            patch("simulation_bridge.src.utils.performance_monitor.logger.debug") as mock_logger_debug:

        monitor_enabled._save_metrics_to_csv(metric)
        mock_file.assert_called_once_with(
            monitor_enabled.csv_path, 'a', newline='', encoding='utf-8')
        mock_logger_debug.assert_any_call(
            "PERFORMANCE - Saved metrics for operation %s to %s",
            op_id,
            monitor_enabled.csv_path
        )


def test_disabled_monitor_skips_methods(monitor_disabled):
    """When disabled, monitor methods should be no-ops."""
    op_id = "op_disabled"

    monitor_disabled.start_operation(op_id)
    assert op_id not in monitor_disabled.metrics_by_operation_id

    monitor_disabled.record_core_received_input(op_id)
    monitor_disabled.record_core_sent_input(op_id)
    monitor_disabled.record_result_sent(op_id)
    monitor_disabled.record_core_received_result(op_id)
    monitor_disabled.finalize_operation(op_id)

    # Should not raise and not record anything
    assert len(monitor_disabled.metrics_history) == 0
