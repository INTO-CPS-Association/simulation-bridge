"""
Performance monitoring utilities for the Simulation Bridge.
"""
import csv
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Any, List

import psutil

from .logger import get_logger

logger = get_logger()

#pylint: disable= too-many-instance-attributes,broad-exception-caught

@dataclass
class PerformanceMetrics:
    """Data class to store performance metrics for a single operation."""
    operation_id: str
    timestamp: float
    request_received_time: float
    core_received_input_time: float
    core_sent_input_time: float
    result_times: List[float] = field(default_factory=list)
    result_sent_time: float = 0.0
    cpu_percent: float = 0.0
    memory_rss_mb: float = 0.0
    total_duration: float = 0.0
    input_overhead: float = 0.0
    output_overhead: float = 0.0
    total_overhead: float = 0.0
    processing_duration: float = 0.0


class PerformanceMonitor:
    """
    A singleton class to monitor and collect performance metrics
    for multiple concurrent operations in the Simulation Bridge.
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(PerformanceMonitor, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if self._initialized:
            return

        self.enabled = False
        self.output_dir = Path('performance_logs')
        self.metrics_by_operation_id: Dict[str, PerformanceMetrics] = {}
        self.metrics_history = []
        self.process = None
        self.csv_path = None

        if config:
            perf_config = config.get('performance', {})
            self.enabled = perf_config.get('enabled', False)
            log_file = perf_config.get(
                'file', 'performance_logs/performance_metrics.csv')

            self.output_dir = Path(log_file).parent
            self.csv_path = Path(log_file)

        if self.enabled:
            try:
                self.output_dir.mkdir(parents=True, exist_ok=True)
                self.process = psutil.Process()

                if not self.csv_path.exists():
                    self._write_csv_headers()
                    logger.debug(
                        "PERFORMANCE - Created performance metrics file: %s",
                        self.csv_path)

                logger.debug(
                    "PERFORMANCE - Performance monitoring enabled. Logs will be saved to %s",
                    self.output_dir)
            except Exception as e:
                logger.error(
                    "Failed to initialize performance monitoring: %s", e)
                self.enabled = False
        else:
            logger.debug("PERFORMANCE - Performance monitoring is disabled")

        self._initialized = True

    def _write_csv_headers(self):
        """Write CSV headers to the output file."""
        if not self.enabled:
            return

        try:
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Operation ID',
                    'Timestamp',
                    'Request Received Time',
                    'Core Received Input Time',
                    'Core Sent Input Time',
                    'Number of Results',
                    'Result Sent Time',
                    'CPU Percent',
                    'Memory RSS (MB)',
                    'Total Duration',
                    'Average Result Interval',
                    'Input Overhead',
                    'Output Overhead',
                    'Total Overhead',
                    'Processing Duration'
                ])
        except Exception as e:
            logger.error("Failed to write CSV headers: %s", e)
            self.enabled = False

    def start_operation(self, operation_id: str):
        """Initialize metrics for a new operation."""
        if not self.enabled:
            return

        metric = PerformanceMetrics(
            operation_id=operation_id,
            timestamp=time.time(),
            request_received_time=time.time(),
            core_received_input_time=0.0,
            core_sent_input_time=0.0
        )
        self.metrics_by_operation_id[operation_id] = metric
        logger.debug(
            "PERFORMANCE - Started monitoring operation %s",
            operation_id)

    def record_core_received_input(self, operation_id: str):
        self._update_timestamp(operation_id, 'core_received_input_time')

    def record_core_sent_input(self, operation_id: str):
        self._update_timestamp(operation_id, 'core_sent_input_time')

    def record_result_sent(self, operation_id: str):
        self._update_timestamp(operation_id, 'result_sent_time')

    def record_core_received_result(self, operation_id: str):
        """Record timestamp of a received partial result."""
        if not self._is_valid_operation(operation_id):
            return
        now = time.time()
        self.metrics_by_operation_id[operation_id].result_times.append(now)
        self._update_system_metrics(self.metrics_by_operation_id[operation_id])
        logger.debug(
            "PERFORMANCE - Recorded core received result for operation %s at %.2fs",
            operation_id,
            now)

    def finalize_operation(self, operation_id: str):
        """Mark an operation as complete and save its metrics."""
        if not self._is_valid_operation(operation_id):
            return

        metric = self.metrics_by_operation_id.pop(operation_id)

        metric.total_duration = time.time() - metric.request_received_time

        if metric.core_sent_input_time and metric.request_received_time:
            metric.input_overhead = metric.core_sent_input_time - metric.request_received_time

        if metric.result_times:
            last_result_time = metric.result_times[-1]
            metric.output_overhead = metric.result_sent_time - last_result_time
            metric.processing_duration = last_result_time - metric.core_sent_input_time

        metric.total_overhead = metric.input_overhead + metric.output_overhead

        self._update_system_metrics(metric)
        self.metrics_history.append(metric)
        self._save_metrics_to_csv(metric)
        logger.debug(
            "PERFORMANCE - Finalized operation %s. Duration: %.2fs",
            operation_id,
            metric.total_duration)

    def _update_timestamp(self, operation_id: str, field_name: str):
        if not self._is_valid_operation(operation_id):
            return
        now = time.time()
        setattr(self.metrics_by_operation_id[operation_id], field_name, now)
        self._update_system_metrics(self.metrics_by_operation_id[operation_id])
        logger.debug(
            "PERFORMANCE - Updated %s for operation %s at %.2fs",
            field_name,
            operation_id,
            now)

    def _update_system_metrics(self, metric: PerformanceMetrics):
        metric.cpu_percent = self.process.cpu_percent()
        metric.memory_rss_mb = self.process.memory_info().rss / (1024 * 1024)
        logger.debug(
            "Updated system metrics for operation %s: CPU %%: %.2f, Memory RSS: %.2f MB",
            metric.operation_id,
            metric.cpu_percent,
            metric.memory_rss_mb
        )

    def _save_metrics_to_csv(self, metric: PerformanceMetrics):
        if not self.enabled:
            return

        # Calculate average interval between results
        avg_result_interval = 0.0
        if len(metric.result_times) > 1:
            intervals = [t2 - t1 for t1,
                         t2 in zip(metric.result_times,
                                   metric.result_times[1:])]
            avg_result_interval = sum(intervals) / len(intervals)

        try:
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    metric.operation_id,
                    metric.timestamp,
                    metric.request_received_time,
                    metric.core_received_input_time,
                    metric.core_sent_input_time,
                    len(metric.result_times),
                    metric.result_sent_time,
                    metric.cpu_percent,
                    metric.memory_rss_mb,
                    metric.total_duration,
                    avg_result_interval,
                    metric.input_overhead,
                    metric.output_overhead,
                    metric.total_overhead,
                    metric.processing_duration
                ])
            logger.debug(
                "PERFORMANCE - Saved metrics for operation %s to %s",
                metric.operation_id,
                self.csv_path)
        except Exception as e:
            logger.error(
                "Failed to save metrics for operation %s: %s",
                metric.operation_id,
                e)

    def _is_valid_operation(self, operation_id: str) -> bool:
        return self.enabled and operation_id in self.metrics_by_operation_id
