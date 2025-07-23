import threading

class CommandRegistry:
    """Global command registry for simulation control."""

    _stop_event = threading.Event()

    @classmethod
    def stop(cls) -> None:
        """Signal that the current simulation should stop."""
        cls._stop_event.set()

    @classmethod
    def reset(cls) -> None:
        """Clear the stop flag, allowing simulations to run."""
        cls._stop_event.clear()

    @classmethod
    def should_stop(cls) -> bool:
        """Check whether a stop command was issued."""
        return cls._stop_event.is_set()