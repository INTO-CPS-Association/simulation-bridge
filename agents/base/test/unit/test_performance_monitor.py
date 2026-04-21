"""Tests for shared performance monitor abstractions."""

import csv

import pytest

from base_agent.utils.performance_monitor import BasePerformanceMonitor


class DummyProcess:
    """Simple psutil.Process test double."""

    class _MemoryInfo:
        rss = 1024 * 1024

    def cpu_percent(self):
        return 5.0

    def memory_info(self):
        return self._MemoryInfo()


class DummyPerformanceMonitor(BasePerformanceMonitor):
    """Concrete monitor used for base monitor tests."""

    engine_label = "DUMMY"


class DummyPsutilModule:
    """psutil module test double."""

    @staticmethod
    def Process():
        return DummyProcess()


@pytest.fixture(autouse=True)
def reset_dummy_monitor_singleton():
    """Reset singleton state between tests."""

    DummyPerformanceMonitor._instance = None
    DummyPerformanceMonitor._initialized = False
    yield
    DummyPerformanceMonitor._instance = None
    DummyPerformanceMonitor._initialized = False


def test_base_performance_monitor_records_and_writes_csv(tmp_path, monkeypatch):
    """Shared monitor should persist metrics and provide summary statistics."""

    monkeypatch.setattr(
        "base_agent.utils.performance_monitor.PSUTIL_MODULE",
        DummyPsutilModule(),
    )

    monitor = DummyPerformanceMonitor(
        config={
            "performance": {
                "enabled": True,
                "log_dir": str(tmp_path),
                "log_filename": "dummy_metrics.csv",
            }
        }
    )
    monitor.start_operation("op-1")
    monitor.record_engine_start()
    monitor.record_engine_startup_complete()
    monitor.record_simulation_complete()
    monitor.record_engine_stop()
    monitor.record_result_sent()
    monitor.complete_operation()

    assert monitor.csv_path.exists()
    with open(monitor.csv_path, "r", encoding="utf-8") as file_obj:
        rows = list(csv.reader(file_obj))

    assert rows[0][3] == "DUMMY Start Time"
    assert len(rows) == 2

    summary = monitor.get_summary()
    assert summary["total_operations"] == 1
