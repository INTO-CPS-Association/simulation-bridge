from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Any, List

import psutil

from .logger import get_logger

logger = get_logger()

# pylint: disable=too-many-instance-attributes,too-many-arguments,too-many-locals,too-many-public-methods, broad-exception-caught

@dataclass
class PerformanceMetrics:
    client_id: str
    client_protocol: str
    operation_id: str
    simulation_type: str
    timestamp: float
    request_received_time: float
    core_received_input_time: float
    core_sent_input_time: float
    result_times: List[float] = field(default_factory=list)
    result_sent_times: List[float] = field(default_factory=list)
    result_completed_time: float = 0.0
    cpu_percent: float = 0.0
    memory_rss_mb: float = 0.0
    total_duration: float = 0.0
    input_overhead: float = 0.0
    output_overheads: List[float] = field(default_factory=list)
    total_overheads: List[float] = field(default_factory=list)

class PerformanceMonitor:
    _instance: Optional[PerformanceMonitor] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if self._initialized:
            return

        self.enabled: bool = False
        self.output_dir: Path = Path("performance_logs")
        self.csv_path: Path = self.output_dir / "performance_metrics.csv"
        self.metrics_by_operation_id: Dict[str, PerformanceMetrics] = {}
        self.metrics_history: List[PerformanceMetrics] = []
        self.process: Optional[psutil.Process] = None

        if config:
            perf_cfg = config.get("performance", {})
            self.enabled = perf_cfg.get("enabled", False)
            log_file = perf_cfg.get("file", str(self.csv_path))
            self.output_dir = Path(log_file).parent
            self.csv_path = Path(log_file)

        if self.enabled:
            try:
                self.output_dir.mkdir(parents=True, exist_ok=True)
                self.process = psutil.Process()
                if not self.csv_path.exists():
                    self._write_csv_headers()
                logger.debug("PERFORMANCE - Logging to %s", self.csv_path)
            except Exception as exc:
                logger.error(
                    "Failed to initialize performance monitoring: %s", exc)
                self.enabled = False
        else:
            logger.debug("PERFORMANCE - Monitoring disabled")

        self._initialized = True

    def _write_csv_headers(self) -> None:
        if not self.enabled:
            return
        try:
            with self.csv_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow([
                    "Timestamp",
                    "Client ID",
                    "Client Protocol",
                    "Operation ID",
                    "Simulation Type",
                    "Request Received Time",
                    "Core Received Input Time",
                    "Core Sent Input Time",
                    "Number of Results",
                    "Result Times",
                    "Result Sent Times",
                    "Simulation Request Completed Time",
                    "CPU Percent",
                    "Memory RSS (MB)",
                    "Total Duration",
                    "Average Result Interval",
                    "Input Overhead",
                    "Output Overheads",
                    "Total Overheads",
                ])
        except Exception as exc:
            logger.error("Failed to write CSV headers: %s", exc)
            self.enabled = False

    def _update_system_metrics(self, metric: PerformanceMetrics) -> None:
        if self.process:
            metric.cpu_percent = self.process.cpu_percent()
            metric.memory_rss_mb = self.process.memory_info().rss / (1024 * 1024)

    def _is_valid_operation(self, operation_id: str) -> bool:
        return self.enabled and operation_id in self.metrics_by_operation_id

    def start_operation(self, operation_id: str, client_id: str = "unknown",
                        protocol: str = "unknown",
                        simulation_type: str = "unknown") -> None:
        if not self.enabled or operation_id in self.metrics_by_operation_id:
            return

        now = time.time()
        self.metrics_by_operation_id[operation_id] = PerformanceMetrics(
            client_id=client_id,
            client_protocol=protocol,
            operation_id=operation_id,
            simulation_type=simulation_type,
            timestamp=now,
            request_received_time=now,
            core_received_input_time=0.0,
            core_sent_input_time=0.0,
        )

    def record_core_received_input(self, operation_id: str) -> None:
        self._update_timestamp(operation_id, "core_received_input_time")

    def record_core_sent_input(self, operation_id: str) -> None:
        self._update_timestamp(operation_id, "core_sent_input_time")

    def record_core_received_result(self, operation_id: str) -> None:
        if not self._is_valid_operation(operation_id):
            return
        now = time.time()
        metric = self.metrics_by_operation_id[operation_id]
        metric.result_times.append(now)
        self._update_system_metrics(metric)

    def record_result_sent(self, operation_id: str) -> None:
        if not self._is_valid_operation(operation_id):
            return
        now = time.time()
        metric = self.metrics_by_operation_id[operation_id]
        metric.result_sent_times.append(now)
        if metric.result_times:
            overhead = now - metric.result_times[-1]
            metric.output_overheads.append(overhead)
        self._update_system_metrics(metric)

    def finalize_operation(self, operation_id: str) -> None:
        if not self._is_valid_operation(operation_id):
            return
        metric = self.metrics_by_operation_id.pop(operation_id)
        metric.result_completed_time = time.time()
        metric.total_duration = metric.result_completed_time - metric.request_received_time
        if metric.core_sent_input_time:
            metric.input_overhead = metric.core_sent_input_time - metric.request_received_time
        metric.total_overheads = [
            metric.input_overhead +
            o for o in metric.output_overheads]
        self._update_system_metrics(metric)
        self.metrics_history.append(metric)
        self._save_metrics_to_csv(metric)

    def _update_timestamp(self, operation_id: str, field_name: str) -> None:
        if not self._is_valid_operation(operation_id):
            return
        now = time.time()
        setattr(self.metrics_by_operation_id[operation_id], field_name, now)
        self._update_system_metrics(self.metrics_by_operation_id[operation_id])

    def _save_metrics_to_csv(self, metric: PerformanceMetrics) -> None:
        if not self.enabled:
            return

        avg_interval = 0.0
        if len(metric.result_times) > 1:
            intervals = [t2 - t1 for t1,
                         t2 in zip(metric.result_times,
                                   metric.result_times[1:])]
            avg_interval = sum(intervals) / len(intervals)

        try:
            with self.csv_path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow([
                    metric.timestamp,
                    metric.client_id,
                    metric.client_protocol,
                    metric.operation_id,
                    metric.simulation_type,
                    metric.request_received_time,
                    metric.core_received_input_time,
                    metric.core_sent_input_time,
                    len(metric.result_times),
                    ";".join(f"{v:.6f}" for v in metric.result_times),
                    ";".join(f"{v:.6f}" for v in metric.result_sent_times),
                    metric.result_completed_time,
                    metric.cpu_percent,
                    metric.memory_rss_mb,
                    metric.total_duration,
                    avg_interval,
                    metric.input_overhead,
                    ";".join(f"{v:.6f}" for v in metric.output_overheads),
                    ";".join(f"{v:.6f}" for v in metric.total_overheads),
                ])
        except Exception as exc:
            logger.error(
                "Failed to save metrics for %s: %s",
                metric.operation_id,
                exc)
