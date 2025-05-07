"""
Configuration manager for the MATLAB Agent.
"""

from pathlib import Path
from typing import Optional, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, ValidationError, ConfigDict

from ..utils.logger import get_logger
from ..utils.config_loader import load_config

logger = get_logger()

# ---------------------------
# Agent Models
# ---------------------------

class BaseModelWithExtraIgnored(BaseModel):
    """Base model with configuration to ignore extra fields."""
    model_config = ConfigDict(extra='ignore')

class Agent(BaseModelWithExtraIgnored):
    agent_id: str = "matlab"

class RabbitMQ(BaseModelWithExtraIgnored):
    host: str = "localhost"
    port: int = 5672
    username: str = "guest"
    password: str = "guest"
    heartbeat: int = 600

class Exchanges(BaseModelWithExtraIgnored):
    input: str = "ex.bridge.output"
    output: str = "ex.sim.result"

class Queue(BaseModelWithExtraIgnored):
    durable: bool = True
    prefetch_count: int = 1

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class Logging(BaseModelWithExtraIgnored):
    level: LogLevel = LogLevel.INFO
    file: str = "logs/matlab_agent.log"

class TCP(BaseModelWithExtraIgnored):
    host: str = "localhost"
    port: int = 5678

class Simulation(BaseModelWithExtraIgnored):
    type: str = "batch"

class SuccessTemplate(BaseModelWithExtraIgnored):
    status: Literal["success"] = "success"
    simulation: Simulation = Simulation()
    timestamp_format: str = "%Y-%m-%dT%H:%M:%SZ"
    include_metadata: bool = True
    metadata_fields: list[str] = ["execution_time", "memory_usage", "matlab_version"]

class ErrorTemplate(BaseModelWithExtraIgnored):
    status: Literal["error"] = "error"
    include_stacktrace: bool = False
    error_codes: Dict[str, int] = {
        "invalid_config": 400,
        "matlab_start_failure": 500,
        "execution_error": 500,
        "timeout": 504,
        "missing_file": 404
    }
    timestamp_format: str = "%Y-%m-%dT%H:%M:%SZ"

class ProgressTemplate(BaseModelWithExtraIgnored):
    status: Literal["in_progress"] = "in_progress"
    include_percentage: bool = True
    update_interval: int = 5
    timestamp_format: str = "%Y-%m-%dT%H:%M:%SZ"

class ResponseTemplates(BaseModelWithExtraIgnored):
    success: SuccessTemplate = SuccessTemplate()
    error: ErrorTemplate = ErrorTemplate()
    progress: ProgressTemplate = ProgressTemplate()

class Config(BaseModelWithExtraIgnored):
    agent: Agent = Agent()
    rabbitmq: RabbitMQ = RabbitMQ()
    exchanges: Exchanges = Exchanges()
    queue: Queue = Queue()
    logging: Logging = Logging()
    tcp: TCP = TCP()
    response_templates: ResponseTemplates = ResponseTemplates()

# ---------------------------
# Configuration Manager
# ---------------------------

class ConfigManager:
    """
    Manager for loading and providing access to application configuration.
    """
    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Initialize the configuration manager.
        
        Args:
            config_path (Optional[str]): Path to the configuration file.
                                         If None, uses the default location.
        """
        self.config_path: Path = Path(config_path) if config_path else Path(__file__).parent.parent.parent / "config" / "config.yaml"
        try:
            raw_config = load_config(self.config_path)
            self.config = self._validate_config(raw_config)
        except (FileNotFoundError, ValidationError) as e:
            logger.warning(f"Configuration error: {str(e)}, using defaults.")
            self.config = self.get_default_config()
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}, using defaults.")
            self.config = self.get_default_config()

    def _validate_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration using Pydantic models."""
        try:
            validated_config = Config(**config_data).model_dump()
            logger.info("Configuration validated successfully.")
            return validated_config
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {str(e)}")
            raise

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration as dictionary."""
        return Config().model_dump()

    def get_config(self) -> Dict[str, Any]:
        """
        Get the loaded configuration.
        
        Returns:
            Dict[str, Any]: Configuration parameters
        """
        return self.config