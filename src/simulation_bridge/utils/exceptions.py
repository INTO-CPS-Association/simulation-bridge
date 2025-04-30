from typing import Optional, Type

class SimulationBridgeError(Exception):
    """Base exception class for all Simulation Bridge exceptions"""
    def __init__(
        self,
        message: str = "An error occurred in Simulation Bridge",
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.original_exception = original_exception
        self.message = message

    def __str__(self) -> str:
        if self.original_exception:
            return f"{self.message}: {str(self.original_exception)}"
        return self.message

class BridgeConfigurationError(SimulationBridgeError):
    """Exception raised for configuration errors"""
    def __init__(self, message: str = "Invalid configuration"):
        super().__init__(f"Configuration Error: {message}")

class ProtocolAdapterError(SimulationBridgeError):
    """Exception raised for protocol adapter errors"""
    def __init__(
        self,
        protocol: str,
        message: str = "Protocol adapter error",
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=f"[{protocol.upper()}] {message}",
            original_exception=original_exception
        )

class ConnectorError(SimulationBridgeError):
    """Exception raised for connector errors"""
    def __init__(
        self,
        connector: str,
        message: str = "Connector error",
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=f"[{connector.upper()}] {message}",
            original_exception=original_exception
        )

class DataTransformationError(SimulationBridgeError):
    """Exception raised for data transformation errors"""
    def __init__(
        self,
        source_format: str,
        target_format: str,
        message: str = "Data transformation failed",
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=f"{message} ({source_format} -> {target_format})",
            original_exception=original_exception
        )

class SimulationStateError(SimulationBridgeError):
    """Exception raised for invalid simulation state transitions"""
    def __init__(
        self,
        current_state: str,
        target_state: str,
        message: str = "Invalid state transition"
    ):
        super().__init__(
            message=f"{message}: {current_state} -> {target_state}"
        )

def error_handler(
    exception_type: Type[SimulationBridgeError],
    message: Optional[str] = None
):
    """Decorator for handling exceptions in async functions"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_message = message or f"Error in {func.__name__}"
                raise exception_type(error_message, original_exception=e) from e
        return wrapper
    return decorator