"""Shared performance monitoring utilities for simulator agents."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any, Dict, Optional, Type

try:
    import psutil as PSUTIL_MODULE
except ModuleNotFoundError:  # pragma: no cover - optional in base package
    PSUTIL_MODULE = None

from .logger import get_logger


@dataclass
class PerformanceMetrics:  # pylint: disable=too-many-instance-attributes
    """Performance metrics captured for a single simulation operation."""

    operation_id: str
    timestamp: float
    request_received_time: float
    engine_start_time: float
    engine_startup_duration: float
    simulation_duration: float
    engine_stop_time: float
    result_send_time: float
    cpu_percent: float
    memory_rss_mb: float
    total_duration: float


class BasePerformanceMonitor:  # pylint: disable=too-many-instance-attributes
    """Collect and persist performance metrics with a simulator-agnostic core."""

    _instance = None
    _initialized = False

    engine_label: str = "ENGINE"
    metrics_class: Type[PerformanceMetrics] = PerformanceMetrics

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BasePerformanceMonitor, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None, logger=None):
        self.logger = logger or get_logger("AGENT")
        if not self._initialized:
            self.enabled = False
            self.output_dir = Path("performance_logs")
            self.current_metrics = None
            self.metrics_history = []
            self.process = None
            self.csv_path = None
            log_filename = "performance_metrics.csv"

            if config:
                perf_config = config.get("performance", {})
                self.enabled = perf_config.get("enabled", False)
                log_dir = perf_config.get("log_dir", "performance_logs")
                log_filename = perf_config.get("log_filename", log_filename)

                if os.path.isabs(log_dir):
                    self.output_dir = Path(log_dir)
                else:
                    self.output_dir = Path.cwd() / log_dir

            if self.enabled:
                try:
                    if PSUTIL_MODULE is None:
                        raise RuntimeError(
                            "psutil is required when performance monitoring is enabled."
                        )
                    self.output_dir.mkdir(parents=True, exist_ok=True)
                    self.logger.debug(
                        "Created performance log directory: %s",
                        self.output_dir,
                    )

                    self.process = PSUTIL_MODULE.Process()
                    self.csv_path = self.output_dir / log_filename

                    if not self.csv_path.exists():
                        self._write_csv_headers()
                        self.logger.debug(
                            "Created performance metrics file: %s",
                            self.csv_path,
                        )

                    self.logger.debug(
                        "Performance monitoring enabled. Logs will be saved to %s",
                        self.output_dir,
                    )
                except Exception as error:  # pylint: disable=broad-exception-caught
                    self.logger.error(
                        "Failed to initialize performance monitoring: %s",
                        error,
                    )
                    self.enabled = False
            else:
                self.logger.debug("Performance monitoring is disabled")

            self._initialized = True

    def _write_csv_headers(self):
        """Write CSV headers to the output file."""

        if not self.enabled:
            return

        try:
            with open(self.csv_path, "w", newline="", encoding="utf-8") as file_obj:
                writer = csv.writer(file_obj)
                writer.writerow(
                    [
                        "Operation ID",
                        "Timestamp",
                        "Request Received Time",
                        f"{self.engine_label} Start Time",
                        f"{self.engine_label} Startup Duration (s)",
                        "Simulation Duration (s)",
                        f"{self.engine_label} Stop Time",
                        "Result Send Time",
                        "CPU Usage (%)",
                        "Memory RSS (MB)",
                        "Total Duration (s)",
                    ]
                )
        except Exception as error:  # pylint: disable=broad-exception-caught
            self.logger.error("Failed to write CSV headers: %s", error)
            self.enabled = False

    def start_operation(self, operation_id: str):
        """Start monitoring an operation by ID."""

        if not self.enabled:
            return

        self.current_metrics = self.metrics_class(
            operation_id=operation_id,
            timestamp=time.time(),
            request_received_time=time.time(),
            engine_start_time=0.0,
            engine_startup_duration=0.0,
            simulation_duration=0.0,
            engine_stop_time=0.0,
            result_send_time=0.0,
            cpu_percent=self.process.cpu_percent(),
            memory_rss_mb=self.process.memory_info().rss / (1024 * 1024),
            total_duration=0.0,
        )
        self.logger.debug("Started monitoring operation %s", operation_id)

    def record_engine_start(self):
        """Record simulation engine start timestamp."""

        if not self.enabled or not self.current_metrics:
            return

        self.current_metrics.engine_start_time = time.time()
        self._update_system_metrics()

    def record_engine_startup_complete(self):
        """Record simulation engine startup completion."""

        if not self.enabled or not self.current_metrics:
            return

        startup_duration = time.time() - self.current_metrics.engine_start_time
        self.current_metrics.engine_startup_duration = startup_duration
        self._update_system_metrics()
        self.logger.debug("%s startup duration: %.2fs", self.engine_label, startup_duration)

    def record_simulation_complete(self):
        """Record end of simulation run."""

        if not self.enabled or not self.current_metrics:
            return

        self.current_metrics.simulation_duration = (
            time.time()
            - self.current_metrics.engine_start_time
            - self.current_metrics.engine_startup_duration
        )
        self._update_system_metrics()

    def record_engine_stop(self):
        """Record simulation engine stop timestamp."""

        if not self.enabled or not self.current_metrics:
            return

        self.current_metrics.engine_stop_time = time.time()
        self._update_system_metrics()

    def record_result_sent(self):
        """Record result publish timestamp."""

        if not self.enabled or not self.current_metrics:
            return

        self.current_metrics.result_send_time = time.time()
        self._update_system_metrics()

    def _update_system_metrics(self):
        """Refresh CPU and memory metrics for current process."""

        if not self.enabled or not self.current_metrics:
            return

        self.current_metrics.cpu_percent = self.process.cpu_percent()
        self.current_metrics.memory_rss_mb = (
            self.process.memory_info().rss / (1024 * 1024)
        )

    def complete_operation(self):
        """Finalize current operation metrics and persist them."""

        if not self.enabled or not self.current_metrics:
            return

        self.current_metrics.total_duration = (
            time.time() - self.current_metrics.request_received_time
        )
        self.metrics_history.append(self.current_metrics)
        self._save_metrics_to_csv(self.current_metrics)
        self.logger.debug(
            "Completed operation %s in %.2fs",
            self.current_metrics.operation_id,
            self.current_metrics.total_duration,
        )
        self.current_metrics = None

    def _save_metrics_to_csv(self, metrics: PerformanceMetrics):
        """Append operation metrics to CSV output."""

        if not self.enabled:
            return

        with open(self.csv_path, "a", newline="", encoding="utf-8") as file_obj:
            writer = csv.writer(file_obj)
            writer.writerow(
                [
                    metrics.operation_id,
                    metrics.timestamp,
                    metrics.request_received_time,
                    metrics.engine_start_time,
                    metrics.engine_startup_duration,
                    metrics.simulation_duration,
                    metrics.engine_stop_time,
                    metrics.result_send_time,
                    metrics.cpu_percent,
                    metrics.memory_rss_mb,
                    metrics.total_duration,
                ]
            )

    def get_summary(self) -> Dict[str, float]:
        """Return aggregate metrics across completed operations."""

        if not self.enabled or not self.metrics_history:
            return {}

        startup_times = [metric.engine_startup_duration for metric in self.metrics_history]
        simulation_times = [metric.simulation_duration for metric in self.metrics_history]
        total_times = [metric.total_duration for metric in self.metrics_history]

        return {
            "avg_startup_time": sum(startup_times) / len(startup_times),
            "min_startup_time": min(startup_times),
            "max_startup_time": max(startup_times),
            "avg_simulation_time": sum(simulation_times) / len(simulation_times),
            "min_simulation_time": min(simulation_times),
            "max_simulation_time": max(simulation_times),
            "avg_total_time": sum(total_times) / len(total_times),
            "min_total_time": min(total_times),
            "max_total_time": max(total_times),
            "total_operations": len(self.metrics_history),
        }


__all__ = ["BasePerformanceMonitor", "PerformanceMetrics"]
