"""
Performance monitoring utilities for the MATLAB agent.
"""
import csv
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

import psutil

from ..utils.logger import get_logger

logger = get_logger()


@dataclass
class PerformanceMetrics:
    """Data class to store performance metrics for a single operation."""
    operation_id: str
    timestamp: float
    request_received_time: float
    matlab_start_time: float
    matlab_startup_duration: float
    simulation_duration: float
    matlab_stop_time: float
    result_send_time: float
    cpu_percent: float
    memory_rss_mb: float
    total_duration: float


class PerformanceMonitor:
    """
    A class to monitor and collect performance metrics for the MATLAB agent.
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(PerformanceMonitor, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the performance monitor.

        Args:
            config (Optional[Dict[str, Any]]): Configuration dictionary containing performance settings
        """
        if not self._initialized:
            self.enabled = False
            self.output_dir = Path('performance_logs')
            self.current_metrics = None
            self.metrics_history = []
            self.process = None
            self.csv_path = None

            if config:
                perf_config = config.get('performance', {})
                self.enabled = perf_config.get('enabled', False)
                log_dir = perf_config.get('log_dir', 'performance_logs')
                log_filename = perf_config.get('log_filename', 'performance_metrics.csv')

                if os.path.isabs(log_dir):
                    self.output_dir = Path(log_dir)
                else:
                    self.output_dir = Path.cwd() / log_dir

            if self.enabled:
                try:
                    self.output_dir.mkdir(parents=True, exist_ok=True)
                    logger.debug("Created performance log directory: %s", self.output_dir)

                    self.process = psutil.Process()
                    self.csv_path = self.output_dir / log_filename

                    if not self.csv_path.exists():
                        self._write_csv_headers()
                        logger.debug("Created performance metrics file: %s", self.csv_path)

                    logger.debug("Performance monitoring enabled. Logs will be saved to %s", 
                               self.output_dir)
                except Exception as e:
                    logger.error("Failed to initialize performance monitoring: %s", e)
                    self.enabled = False
            else:
                logger.debug("Performance monitoring is disabled")

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
                    'MATLAB Start Time',
                    'MATLAB Startup Duration (s)',
                    'Simulation Duration (s)',
                    'MATLAB Stop Time',
                    'Result Send Time',
                    'CPU Usage (%)',
                    'Memory RSS (MB)',
                    'Total Duration (s)'
                ])
        except Exception as e:
            logger.error("Failed to write CSV headers: %s", e)
            self.enabled = False

    def start_operation(self, operation_id: str):
        """
        Start monitoring a new operation.

        Args:
            operation_id (str): Unique identifier for the operation
        """
        if not self.enabled:
            return

        self.current_metrics = PerformanceMetrics(
            operation_id=operation_id,
            timestamp=time.time(),
            request_received_time=time.time(),
            matlab_start_time=0.0,
            matlab_startup_duration=0.0,
            simulation_duration=0.0,
            matlab_stop_time=0.0,
            result_send_time=0.0,
            cpu_percent=self.process.cpu_percent(),
            memory_rss_mb=self.process.memory_info().rss / (1024 * 1024),
            total_duration=0.0
        )
        logger.debug("Started monitoring operation %s", operation_id)

    def record_matlab_start(self):
        """Record the start of MATLAB engine initialization."""
        if not self.enabled or not self.current_metrics:
            return

        self.current_metrics.matlab_start_time = time.time()
        self._update_system_metrics()

    def record_matlab_startup_complete(self):
        """Record the completion of MATLAB engine initialization."""
        if not self.enabled or not self.current_metrics:
            return

        startup_duration = time.time() - self.current_metrics.matlab_start_time
        self.current_metrics.matlab_startup_duration = startup_duration
        self._update_system_metrics()
        logger.debug("MATLAB startup duration: %.2fs", startup_duration)

    def record_simulation_complete(self):
        """Record the completion of the simulation."""
        if not self.enabled or not self.current_metrics:
            return

        self.current_metrics.simulation_duration = (
            time.time() - self.current_metrics.matlab_start_time
        )
        self._update_system_metrics()

    def record_matlab_stop(self):
        """Record the stop of MATLAB engine."""
        if not self.enabled or not self.current_metrics:
            return

        self.current_metrics.matlab_stop_time = time.time()
        self._update_system_metrics()

    def record_result_sent(self):
        """Record when results are sent."""
        if not self.enabled or not self.current_metrics:
            return

        self.current_metrics.result_send_time = time.time()
        self._update_system_metrics()

    def _update_system_metrics(self):
        """Update system resource metrics."""
        if not self.enabled or not self.current_metrics:
            return

        self.current_metrics.cpu_percent = self.process.cpu_percent()
        self.current_metrics.memory_rss_mb = (
            self.process.memory_info().rss / (1024 * 1024)
        )

    def complete_operation(self):
        """Complete the current operation and save metrics."""
        if not self.enabled or not self.current_metrics:
            return

        self.current_metrics.total_duration = (
            time.time() - self.current_metrics.request_received_time
        )
        self.metrics_history.append(self.current_metrics)
        self._save_metrics_to_csv(self.current_metrics)
        logger.debug(
            "Completed operation %s in %.2fs",
            self.current_metrics.operation_id,
            self.current_metrics.total_duration
        )
        self.current_metrics = None

    def _save_metrics_to_csv(self, metrics: PerformanceMetrics):
        """
        Save metrics to CSV file.

        Args:
            metrics (PerformanceMetrics): The metrics to save
        """
        if not self.enabled:
            return

        with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                metrics.operation_id,
                metrics.timestamp,
                metrics.request_received_time,
                metrics.matlab_start_time,
                metrics.matlab_startup_duration,
                metrics.simulation_duration,
                metrics.matlab_stop_time,
                metrics.result_send_time,
                metrics.cpu_percent,
                metrics.memory_rss_mb,
                metrics.total_duration
            ])

    def get_summary(self) -> Dict[str, float]:
        """
        Get a summary of performance metrics across all operations.

        Returns:
            Dict[str, float]: Summary statistics
        """
        if not self.enabled or not self.metrics_history:
            return {}

        startup_times = [m.matlab_startup_duration for m in self.metrics_history]
        simulation_times = [m.simulation_duration for m in self.metrics_history]
        total_times = [m.total_duration for m in self.metrics_history]

        return {
            'avg_startup_time': sum(startup_times) / len(startup_times),
            'min_startup_time': min(startup_times),
            'max_startup_time': max(startup_times),
            'avg_simulation_time': sum(simulation_times) / len(simulation_times),
            'min_simulation_time': min(simulation_times),
            'max_simulation_time': max(simulation_times),
            'avg_total_time': sum(total_times) / len(total_times),
            'min_total_time': min(total_times),
            'max_total_time': max(total_times),
            'total_operations': len(self.metrics_history)
        }
