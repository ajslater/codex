"""Logging classes."""
# TODO move to codex/logger
import logging

from logging.handlers import QueueHandler

from codex.logger.mp_queue import LOG_QUEUE
from codex.settings.settings import LOGLEVEL


class CodexQueueHandler(QueueHandler):
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


LOG_HANDLER = CodexQueueHandler(LOG_QUEUE)


def get_logger(name=None, queue=LOG_QUEUE):
    """Get the logger with only one handler."""
    logger = logging.getLogger(name)
    logger.setLevel(LOGLEVEL)

    keep = None
    for handler in logger.handlers:
        if getattr(handler, "queue", None) == queue:
            keep = handler
            break

    for handler in logger.handlers:
        if handler != keep:
            logger.removeHandler(handler)

    if not logger.handlers:
        if queue == LOG_QUEUE:
            handler = LOG_HANDLER
        else:
            handler = CodexQueueHandler(queue)
        logger.addHandler(handler)
    return logger
