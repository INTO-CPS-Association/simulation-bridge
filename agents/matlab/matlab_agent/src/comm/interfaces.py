"""Compatibility re-exports for shared communication interfaces."""

from base_agent.comm.interfaces import IMessageBroker, IMessageHandler

__all__ = ["IMessageBroker", "IMessageHandler"]
