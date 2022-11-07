"""Logging classes."""
import logging
import os

from logging.handlers import QueueHandler

from codex.logger.log_queue import LOG_QUEUE, CodexLogger


LOG_EVERY = 5


class CodexDjangoQueueHandler(QueueHandler):
    """Special QueueHandler that removes unpickable elements."""

    def enqueue(self, record):
        """Remove unserializable element before queueing."""
        try:
            # Fixes _pickle.PicklingError: Cannot pickle ResolverMatch.
            # Somewhere inside request is this unpicklable object.
            record.__dict__["request"].resolver_match = None
        except KeyError:
            pass
        super().enqueue(record)


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
    handlers = (CodexDjangoQueueHandler(LOG_QUEUE),)
    logging.basicConfig(level=level, format="%(message)s", handlers=handlers)


def get_logger(*args, **kwargs) -> CodexLogger:
    """Pacify pyright."""
    return logging.getLogger(*args, **kwargs)  # type: ignore
