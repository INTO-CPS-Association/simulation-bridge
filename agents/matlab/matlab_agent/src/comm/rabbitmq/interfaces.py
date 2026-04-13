"""Compatibility re-exports for shared RabbitMQ interfaces."""

from base_agent.comm.rabbitmq.interfaces import (
    IRabbitMQManager,
    IRabbitMQMessageHandler,
)

__all__ = ["IRabbitMQManager", "IRabbitMQMessageHandler"]
