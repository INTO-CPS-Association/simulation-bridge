"""Backward-compatible MATLAB connect imports backed by base_agent."""

from base_agent.comm.connect import (
    BROKER_CONNECTION_FAILED_ERROR,
    BROKER_NOT_INITIALIZED_ERROR,
    BROKER_OR_HANDLER_NOT_INITIALIZED_ERROR,
    Connect,
)

__all__ = [
    "BROKER_CONNECTION_FAILED_ERROR",
    "BROKER_NOT_INITIALIZED_ERROR",
    "BROKER_OR_HANDLER_NOT_INITIALIZED_ERROR",
    "Connect",
]
