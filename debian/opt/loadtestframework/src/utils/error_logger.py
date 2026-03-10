"""
Centralized error logging utility.
Logs all errors to error_log.txt in the configured results directory.
"""

import logging
import os

_logger = None
_log_dir = None

ERROR_LOG_FILENAME = "error_log.txt"


def init_error_logger(results_dir: str) -> None:
    """Initialize the error logger to write to the given results directory.

    Must be called once at startup (from orchestrate.py or worker.py)
    before any log_error() calls.  Subsequent calls are ignored.

    Args:
        results_dir: Path to the results/report directory.
    """
    global _logger, _log_dir
    if _logger is not None:
        return  # Already initialised

    _log_dir = results_dir
    os.makedirs(_log_dir, exist_ok=True)

    _logger = logging.getLogger("loadtest_error")
    _logger.setLevel(logging.ERROR)
    if not _logger.handlers:
        log_path = os.path.join(_log_dir, ERROR_LOG_FILENAME)
        handler = logging.FileHandler(log_path, mode="a")
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
        handler.setFormatter(formatter)
        _logger.addHandler(handler)


def get_error_logger() -> logging.Logger:
    """Get or create the singleton error logger.

    If init_error_logger() was not called yet, falls back to writing
    error_log.txt in the current working directory.
    """
    global _logger
    if _logger is not None:
        return _logger

    # Fallback: no explicit init — write to cwd
    fallback_dir = os.getenv("ERROR_LOG_PATH", ".")
    init_error_logger(fallback_dir)
    return _logger


def log_error(module: str, function: str, error, context: str = ""):
    """Log an error with context to error_log.txt.

    Args:
        module: Name of the module where the error occurred.
        function: Name of the function where the error occurred.
        error: The exception or error message.
        context: Optional additional context string.
    """
    logger = get_error_logger()
    msg = f"[{module}.{function}] {type(error).__name__}: {error}"
    if context:
        msg += f" | Context: {context}"
    logger.error(msg)
