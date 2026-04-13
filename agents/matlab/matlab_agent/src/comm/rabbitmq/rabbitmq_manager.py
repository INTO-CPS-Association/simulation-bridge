"""MATLAB RabbitMQ manager wrapper over shared base-agent implementation."""

from typing import Any, Dict

import pika
import yaml
from base_agent.comm.rabbitmq.rabbitmq_manager import (
    RabbitMQManager as BaseRabbitMQManager,
)

from ...utils.logger import get_logger

logger = get_logger()


class RabbitMQManager(BaseRabbitMQManager):
    """MATLAB-specific RabbitMQ manager with shared behavior."""

    def __init__(self, agent_id: str, config: Dict[str, Any]) -> None:
        super().__init__(
            agent_id=agent_id,
            config=config,
            logger=logger,
            pika_module=pika,
            yaml_module=yaml,
        )

    def setup_infrastructure(self) -> None:
        """Set up infrastructure and preserve MATLAB process-exit semantics."""
        try:
            super().setup_infrastructure()
        except RuntimeError:
            raise SystemExit(1) from None
