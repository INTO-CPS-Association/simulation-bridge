import threading

class StopRequested(Exception):
    """Raised to unwind the stack when a stop is requested."""
    pass

class CommandRegistry:
    _stop_event = threading.Event()

    @classmethod
    def stop(cls) -> None:
        cls._stop_event.set()

    @classmethod
    def reset(cls) -> None:
        cls._stop_event.clear()

    @classmethod
    def should_stop(cls) -> bool:
        return cls._stop_event.is_set()

    @classmethod
    def wait(cls, timeout: float) -> bool:
        """Block up to `timeout` seconds. Return True if stop requested."""
        return cls._stop_event.wait(timeout)