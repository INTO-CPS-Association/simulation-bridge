"""MATLAB communication wrapper built on shared base-agent connect implementation."""

from typing import Any, Dict

from base_agent.comm.connect import (
    Connect as BaseConnect,
)
from ..utils.logger import get_logger
from .rabbitmq.message_handler import MessageHandler
from .rabbitmq.rabbitmq_manager import RabbitMQManager

logger = get_logger()


class Connect(BaseConnect):
    """MATLAB-specific connect wrapper with shared behavior."""

    def __init__(
        self,
        agent_id: str,
        config: Dict[str, Any],
        broker_type: str = "rabbitmq",
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            config=config,
            broker_type=broker_type,
            broker_factory=RabbitMQManager,
            message_handler_factory=MessageHandler,
            logger=logger,
        )

    def close(self) -> None:
        """Close MATLAB broker resources with backwards-compatible logging."""
        if self.broker:
            self.broker.close()
        else:
            logger.warning("Attempted to close a non-initialized broker")
