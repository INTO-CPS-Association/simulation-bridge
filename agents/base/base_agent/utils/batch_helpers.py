"""Shared helper utilities for batch simulation handlers."""

from __future__ import annotations

from typing import Any, Callable, Dict, Protocol


class ResultBroker(Protocol):  # pylint: disable=too-few-public-methods
    """Protocol for message broker methods used by batch helpers."""

    def send_result(self, destination: str, result: Dict[str, Any]) -> bool:
        """Send a result payload to the destination route."""


def send_progress_update(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    broker: ResultBroker,
    source: str,
    sim_file: str,
    percentage: int,
    response_templates: Dict[str, Any],
    response_builder: Callable[..., Dict[str, Any]],
    bridge_meta: str = "unknown",
    request_id: str = "unknown",
) -> None:
    """Publish a batch progress response when percentage reporting is enabled."""
    if response_templates.get("progress", {}).get("include_percentage", False):
        progress_response = response_builder(
            "progress",
            sim_file,
            "batch",
            response_templates,
            percentage=percentage,
            bridge_meta=bridge_meta,
            request_id=request_id,
        )
        broker.send_result(source, progress_response)


__all__ = ["ResultBroker", "send_progress_update"]
