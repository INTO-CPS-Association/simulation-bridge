"""Performance monitoring utilities for the MATLAB agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from base_agent.utils.logger import get_logger
from base_agent.utils.performance_monitor import (
    BasePerformanceMonitor,
    PerformanceMetrics as BasePerformanceMetrics,
)

logger = get_logger("MATLAB-AGENT")


@dataclass
class PerformanceMetrics(BasePerformanceMetrics):
    """MATLAB compatibility layer for performance metric attribute names."""

    @property
    def matlab_start_time(self) -> float:
        """Backwards-compatible alias for engine_start_time."""

        return self.engine_start_time

    @matlab_start_time.setter
    def matlab_start_time(self, value: float) -> None:
        self.engine_start_time = value

    @property
    def matlab_startup_duration(self) -> float:
        """Backwards-compatible alias for engine_startup_duration."""

        return self.engine_startup_duration

    @matlab_startup_duration.setter
    def matlab_startup_duration(self, value: float) -> None:
        self.engine_startup_duration = value

    @property
    def matlab_stop_time(self) -> float:
        """Backwards-compatible alias for engine_stop_time."""

        return self.engine_stop_time

    @matlab_stop_time.setter
    def matlab_stop_time(self, value: float) -> None:
        self.engine_stop_time = value


class PerformanceMonitor(BasePerformanceMonitor):
    """MATLAB performance monitor implemented on top of shared base utilities."""

    engine_label = "MATLAB"
    metrics_class = PerformanceMetrics

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config=config, logger=logger)

    def record_matlab_start(self):
        """Backwards-compatible alias for record_engine_start."""

        self.record_engine_start()

    def record_matlab_startup_complete(self):
        """Backwards-compatible alias for record_engine_startup_complete."""

        self.record_engine_startup_complete()

    def record_matlab_stop(self):
        """Backwards-compatible alias for record_engine_stop."""

        self.record_engine_stop()


__all__ = ["PerformanceMetrics", "PerformanceMonitor"]
