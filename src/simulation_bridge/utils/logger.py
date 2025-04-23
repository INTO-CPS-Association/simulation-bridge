import logging
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "logs" / "simulation_bridge.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_FORMAT = "%(asctime)s %(name)s [%(levelname)s] %(message)s"

def setup_logging(level: int = logging.INFO, log_file: Path = LOG_FILE):
    """
    Configura logging globale + silenzia moduli verbosi.
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Pulisce eventuali handler esistenti
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(DEFAULT_FORMAT)

    # Console
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # File
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logging.getLogger("pika").setLevel(logging.CRITICAL)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

def get_logger(name: str = __name__) -> logging.Logger:
    return logging.getLogger(name)
