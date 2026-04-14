"""Tests for MATLAB performance monitor compatibility wrappers."""

import csv

import pytest

from src.utils.performance_monitor import PerformanceMetrics, PerformanceMonitor


class DummyProcess:
    """Simple psutil.Process test double."""

    class _MemoryInfo:
        rss = 1024 * 1024

    def cpu_percent(self):
        return 3.0

    def memory_info(self):
        return self._MemoryInfo()


@pytest.fixture(autouse=True)
def reset_monitor_singleton():
    """Reset singleton state between tests."""

    PerformanceMonitor._instance = None
    PerformanceMonitor._initialized = False
    yield
    PerformanceMonitor._instance = None
    PerformanceMonitor._initialized = False


def test_matlab_metrics_alias_properties():
    """MATLAB alias properties should map to shared engine metric fields."""

    metrics = PerformanceMetrics(
        operation_id="op-1",
        timestamp=0.0,
        request_received_time=0.0,
        engine_start_time=0.0,
        engine_startup_duration=0.0,
        simulation_duration=0.0,
        engine_stop_time=0.0,
        result_send_time=0.0,
        cpu_percent=0.0,
        memory_rss_mb=0.0,
        total_duration=0.0,
    )

    metrics.matlab_start_time = 1.5
    metrics.matlab_startup_duration = 2.5
    metrics.matlab_stop_time = 3.5

    assert metrics.engine_start_time == 1.5
    assert metrics.engine_startup_duration == 2.5
    assert metrics.engine_stop_time == 3.5


def test_matlab_monitor_compatibility_methods(tmp_path, monkeypatch):
    """Legacy MATLAB monitor methods should still record and write metrics."""

    monkeypatch.setattr(
        "base_agent.utils.performance_monitor.PSUTIL_MODULE.Process",
        lambda: DummyProcess(),
    )

    monitor = PerformanceMonitor(
        config={
            "performance": {
                "enabled": True,
                "log_dir": str(tmp_path),
                "log_filename": "matlab_metrics.csv",
            }
        }
    )
    monitor.start_operation("mat-op")
    monitor.record_matlab_start()
    monitor.record_matlab_startup_complete()
    monitor.record_simulation_complete()
    monitor.record_matlab_stop()
    monitor.record_result_sent()
    monitor.complete_operation()

    assert monitor.csv_path.exists()
    with open(monitor.csv_path, "r", encoding="utf-8") as file_obj:
        rows = list(csv.reader(file_obj))

    assert rows[0][3] == "MATLAB Start Time"
    assert monitor.metrics_history[0].matlab_start_time >= 0.0
