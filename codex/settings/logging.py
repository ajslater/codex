"""Logging classes."""
import logging
import os

from logging.handlers import QueueHandler

from codex.logger.log_queue import LOG_QUEUE, CodexLogger


LOG_EVERY = 5


def _get_log_level(debug):
    """Get the log level."""
    environ_loglevel = os.environ.get("LOGLEVEL")
    if environ_loglevel:
        level = environ_loglevel
    elif debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    return level


def init_logging(debug):
    """Initialize logging."""
    level = _get_log_level(debug)
    handlers = (QueueHandler(LOG_QUEUE),)
    logging.basicConfig(level=level, format="%(message)s", handlers=handlers)


def get_logger(*args, **kwargs) -> CodexLogger:
    """Pacify pyright."""
    return logging.getLogger(*args, **kwargs)  # type: ignore
