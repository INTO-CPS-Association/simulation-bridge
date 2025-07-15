from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple
from enum import Enum

import psutil

from .logger import get_logger

logger = get_logger()

# pylint: disable=too-many-instance-attributes,too-many-arguments, too-many-positional-arguments
# pylint: disable=too-many-locals,too-many-public-methods,broad-exception-caught

# (operation_id, protocol, client_id, simulation_type)
KeyT = Tuple[str, str, str, str]


def _make_key(
    operation_id: str,
    protocol: str,
    client_id: str,
    simulation_type: str,
) -> KeyT:
    """Helper to build the extended key consistently."""
    return operation_id, protocol, client_id, simulation_type


@dataclass
class PerformanceMetrics:
    """Metrics collected for a single operation."""
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


@dataclass
class _Paths:
    """Internal storage for output paths."""
    output_dir: Path = Path("performance_logs")
    csv_path: Path = field(
        default_factory=lambda: Path("performance_logs/performance_metrics.csv")
    )


@dataclass
class _RuntimeState:
    """Internal runtime state for the monitor."""
    metrics_by_operation_id: Dict[KeyT, PerformanceMetrics] = field(
        default_factory=dict)
    metrics_history: List[PerformanceMetrics] = field(default_factory=list)
    process: Optional[psutil.Process] = None


class EventType(Enum):
    """Supported performance events."""
    CORE_RECEIVED_INPUT = "core_received_input"
    CORE_SENT_INPUT = "core_sent_input"
    CORE_RECEIVED_RESULT = "core_received_result"
    RESULT_SENT = "result_sent"


class PerformanceMonitor:
    _instance: Optional["PerformanceMonitor"] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):  # noqa: D401  (simple returns)
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if self._initialized:
            return

        self._enabled: bool = False
        self.paths = _Paths()
        self._state = _RuntimeState()

        if config:
            perf_cfg = config.get("performance", {})
            self._enabled = perf_cfg.get("enabled", False)
            log_file = perf_cfg.get("file", str(self.paths.csv_path))
            self.paths.output_dir = Path(log_file).parent
            self.paths.csv_path = Path(log_file)

        if self._enabled:
            try:
                self.paths.output_dir.mkdir(parents=True, exist_ok=True)
                self._state.process = psutil.Process()
                if not self.paths.csv_path.exists():
                    self._write_csv_headers()
                logger.debug("PERFORMANCE - Logging to %s", self.paths.csv_path)
            except Exception as exc:  # pragma: no cover
                logger.error(
                    "Failed to initialize performance monitoring: %s", exc)
                self._enabled = False
        else:
            logger.debug("PERFORMANCE - Monitoring disabled")

        self._initialized = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def history(self) -> List[PerformanceMetrics]:
        return list(self._state.metrics_history)

    def get_metric(
        self,
        operation_id: str,
        protocol: str,
        client_id: str,
        simulation_type: str,
    ) -> Optional[PerformanceMetrics]:
        return self._state.metrics_by_operation_id.get(
            _make_key(operation_id, protocol, client_id, simulation_type)
        )

    def _is_valid_operation(
        self,
        operation_id: str,
        protocol: str,
        client_id: str,
        simulation_type: str,
    ) -> bool:
        return self._enabled and _make_key(
            operation_id, protocol, client_id, simulation_type
        ) in self._state.metrics_by_operation_id

    def _write_csv_headers(self) -> None:
        if not self._enabled:
            return
        try:
            with self.paths.csv_path.open("w", newline="", encoding="utf-8") as fh:
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
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to write CSV headers: %s", exc)
            self._enabled = False

    def _update_system_metrics(self, metric: PerformanceMetrics) -> None:
        if self._state.process:
            metric.cpu_percent = self._state.process.cpu_percent()
            metric.memory_rss_mb = self._state.process.memory_info().rss / (1024 * 1024)

    def start_operation(
        self,
        operation_id: str,
        *,
        client_id: str = "unknown",
        protocol: str = "unknown",
        simulation_type: str = "unknown",
    ) -> None:
        key = _make_key(operation_id, protocol, client_id, simulation_type)
        if not self._enabled or key in self._state.metrics_by_operation_id:
            return

        now = time.time()
        self._state.metrics_by_operation_id[key] = PerformanceMetrics(
            client_id=client_id,
            client_protocol=protocol,
            operation_id=operation_id,
            simulation_type=simulation_type,
            timestamp=now,
            request_received_time=now,
            core_received_input_time=0.0,
            core_sent_input_time=0.0,
        )

    def record_core_received_input(
        self,
        operation_id: str,
        protocol: str,
        client_id: str,
        simulation_type: str,
    ) -> None:
        self.record_event(
            operation_id, protocol, client_id, simulation_type, EventType.CORE_RECEIVED_INPUT
        )

    def record_core_sent_input(
        self,
        operation_id: str,
        protocol: str,
        client_id: str,
        simulation_type: str,
    ) -> None:
        self.record_event(
            operation_id, protocol, client_id, simulation_type, EventType.CORE_SENT_INPUT
        )

    def record_core_received_result(
        self,
        operation_id: str,
        protocol: str,
        client_id: str,
        simulation_type: str,
    ) -> None:
        self.record_event(
            operation_id, protocol, client_id, simulation_type, EventType.CORE_RECEIVED_RESULT
        )

    def record_result_sent(
        self,
        operation_id: str,
        protocol: str,
        client_id: str,
        simulation_type: str,
    ) -> None:
        self.record_event(
            operation_id, protocol, client_id, simulation_type, EventType.RESULT_SENT
        )

    def record_event(
        self,
        operation_id: str,
        protocol: str,
        client_id: str,
        simulation_type: str,
        event: EventType,
    ) -> None:
        if not self._is_valid_operation(
                operation_id, protocol, client_id, simulation_type):
            return

        key = _make_key(operation_id, protocol, client_id, simulation_type)
        now = time.time()
        metric = self._state.metrics_by_operation_id[key]

        if event == EventType.CORE_RECEIVED_INPUT:
            metric.core_received_input_time = now
        elif event == EventType.CORE_SENT_INPUT:
            metric.core_sent_input_time = now
        elif event == EventType.CORE_RECEIVED_RESULT:
            metric.result_times.append(now)
        elif event == EventType.RESULT_SENT:
            metric.result_sent_times.append(now)
            if metric.result_times:
                metric.output_overheads.append(now - metric.result_times[-1])

        self._update_system_metrics(metric)

    def finalize_operation(
        self,
        operation_id: str,
        protocol: str,
        client_id: str,
        simulation_type: str,
    ) -> None:
        if not self._is_valid_operation(
                operation_id, protocol, client_id, simulation_type):
            return

        key = _make_key(operation_id, protocol, client_id, simulation_type)
        metric = self._state.metrics_by_operation_id.pop(key)

        metric.result_completed_time = time.time()
        metric.total_duration = metric.result_completed_time - metric.request_received_time
        if metric.core_sent_input_time:
            metric.input_overhead = metric.core_sent_input_time - metric.request_received_time

        metric.total_overheads = [
            metric.input_overhead +
            o for o in metric.output_overheads]

        self._update_system_metrics(metric)
        self._state.metrics_history.append(metric)
        self._save_metrics_to_csv(metric)

    def _update_timestamp(
        self,
        operation_id: str,
        protocol: str,
        client_id: str,
        simulation_type: str,
        field_name: str,
    ) -> None:
        if not self._is_valid_operation(
                operation_id, protocol, client_id, simulation_type):
            return
        key = _make_key(operation_id, protocol, client_id, simulation_type)
        now = time.time()
        setattr(self._state.metrics_by_operation_id[key], field_name, now)
        self._update_system_metrics(self._state.metrics_by_operation_id[key])

    def _save_metrics_to_csv(self, metric: PerformanceMetrics) -> None:
        if not self._enabled:
            return

        avg_interval = 0.0
        if len(metric.result_times) > 1:
            intervals = [t2 - t1 for t1,
                         t2 in zip(metric.result_times,
                                   metric.result_times[1:])]
            avg_interval = sum(intervals) / len(intervals)

        try:
            with self.paths.csv_path.open("a", newline="", encoding="utf-8") as fh:
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
        except Exception as exc:  # pragma: no cover
            logger.error(
                "Failed to save metrics for %s: %s",
                metric.operation_id,
                exc)
