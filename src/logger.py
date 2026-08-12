"""
Unified logging — console + rotating file.

Usage:
    from src.logger import get_logger
    logger = get_logger(__name__)
"""

import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "run.log")
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 3
_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%dT%H:%M:%S"

_initialized = False


def _ensure_log_dir():
    """Create the logs/ directory if it doesn't exist."""
    os.makedirs(_LOG_DIR, exist_ok=True)


def setup_logging(level=logging.INFO):
    """Configure the root logger once. Safe to call multiple times."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    _ensure_log_dir()

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FMT)

    # Console handler using Rich
    from rich.logging import RichHandler
    console = RichHandler(rich_tracebacks=True, markup=True, show_time=False, show_path=False)
    console.setLevel(level)
    # The file handler needs a formatter, but RichHandler handles formatting itself
    file_formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FMT)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(file_handler)

    # Silence noisy third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("ddgs").setLevel(logging.WARNING)
    logging.getLogger("curl_cffi").setLevel(logging.WARNING)
    logging.getLogger("WDM").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Initializes logging on first call."""
    setup_logging()
    return logging.getLogger(name)
