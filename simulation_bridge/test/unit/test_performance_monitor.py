"""
Test suite for PerformanceMonitor and PerformanceMetrics.
"""
from unittest.mock import patch, MagicMock, mock_open
import pytest

from simulation_bridge.src.utils.performance_monitor import PerformanceMonitor

# pylint: disable=redefined-outer-name,protected-access,line-too-long,unused-argument


@pytest.fixture
def config_enabled(tmp_path):
    log_file = tmp_path / "performance_logs" / "performance_metrics.csv"
    return {
        "performance": {
            "enabled": True,
            "file": str(log_file),
        }
    }


@pytest.fixture
def config_disabled():
    return {"performance": {"enabled": False}}


@pytest.fixture
def monitor_enabled(config_enabled):
    PerformanceMonitor._instance = None
    PerformanceMonitor._initialized = False
    monitor = PerformanceMonitor(config_enabled)
    yield monitor
    PerformanceMonitor._instance = None
    PerformanceMonitor._initialized = False


@pytest.fixture
def monitor_disabled(config_disabled):
    PerformanceMonitor._instance = None
    PerformanceMonitor._initialized = False
    monitor = PerformanceMonitor(config_disabled)
    yield monitor
    PerformanceMonitor._instance = None
    PerformanceMonitor._initialized = False


def test_singleton_behavior(config_enabled):
    PerformanceMonitor._instance = None
    PerformanceMonitor._initialized = False
    m1 = PerformanceMonitor(config_enabled)
    m2 = PerformanceMonitor(config_enabled)
    assert m1 is m2


def test_initialization_creates_dir_and_file(tmp_path, config_enabled):
    with (
        patch("simulation_bridge.src.utils.performance_monitor.psutil.Process") as mock_process,
        patch("pathlib.Path.open", mock_open()) as mock_file,
        patch("pathlib.Path.mkdir") as mock_mkdir,
    ):
        mock_process.return_value = MagicMock()
        PerformanceMonitor._instance = None
        PerformanceMonitor._initialized = False

        monitor = PerformanceMonitor(config_enabled) # pylint: disable=unused-variable

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_file.assert_called()


def test_start_operation_creates_metric(monitor_enabled):
    op_id = "op1"
    monitor_enabled.start_operation(
        op_id, client_id="c1", protocol="rest", simulation_type="batch")

    metric = monitor_enabled.get_metric(op_id)
    assert metric is not None
    assert metric.operation_id == op_id
    assert metric.timestamp > 0
    assert metric.client_id == "c1"
    assert metric.client_protocol == "rest"
    assert metric.simulation_type == "batch"


def test_record_timestamps_update_fields(monitor_enabled):
    op_id = "op2"
    monitor_enabled.start_operation(
        op_id, client_id="c1", protocol="rest", simulation_type="batch")

    with patch("time.time", return_value=1234.5):
        monitor_enabled.record_core_received_input(op_id)
        metric = monitor_enabled.get_metric(op_id)
        assert metric and metric.core_received_input_time == pytest.approx(1234.5)

        monitor_enabled.record_core_sent_input(op_id)
        metric = monitor_enabled.get_metric(op_id)
        assert metric and metric.core_sent_input_time == pytest.approx(1234.5)


def test_record_core_received_result_appends_time_and_updates_metrics(monitor_enabled):
    op_id = "op3"
    monitor_enabled.start_operation(
        op_id, client_id="c1", protocol="rest", simulation_type="batch")
    with (
        patch("time.time", return_value=1000.0),
        patch.object(monitor_enabled, "_update_system_metrics") as mock_update,
    ):
        monitor_enabled.record_core_received_result(op_id)
        metric = monitor_enabled.get_metric(op_id)
        assert metric.result_times[-1] == pytest.approx(1000.0)
        mock_update.assert_called_once_with(metric)


def test_finalize_operation_calculates_metrics_and_saves(monitor_enabled):
    op_id = "op4"
    monitor_enabled.start_operation(
        op_id, client_id="c1", protocol="rest", simulation_type="batch")
    metric = monitor_enabled.get_metric(op_id)

    metric.request_received_time = 1.0
    metric.core_sent_input_time = 2.0
    metric.result_times = [3.0, 4.0, 5.0]
    metric.output_overheads = [1.0, 1.0, 1.0]

    with (
        patch("time.time", return_value=10.0),
        patch.object(monitor_enabled, "_save_metrics_to_csv") as mock_save,
        patch.object(monitor_enabled, "_update_system_metrics") as mock_update,
    ):
        monitor_enabled.finalize_operation(op_id)

        assert monitor_enabled.get_metric(op_id) is None
        assert metric.total_duration == pytest.approx(9.0, abs=0.1)
        assert metric.input_overhead == pytest.approx(1.0, abs=0.1)
        assert metric.total_overheads == [2.0, 2.0, 2.0]

        mock_save.assert_called_once_with(metric)
        mock_update.assert_called()

def test_disabled_monitor_skips_methods(monitor_disabled):
    op_id = "op_disabled"
    monitor_disabled.start_operation(
        op_id, client_id="c1", protocol="rest", simulation_type="batch")
    monitor_disabled.record_core_received_input(op_id)
    monitor_disabled.record_core_sent_input(op_id)
    monitor_disabled.record_result_sent(op_id)
    monitor_disabled.record_core_received_result(op_id)
    monitor_disabled.finalize_operation(op_id)

    assert monitor_disabled.get_metric(op_id) is None
    assert len(monitor_disabled.history) == 0
