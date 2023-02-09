"""Logging classes."""
# TODO move to codex/logger
import logging

from logging.handlers import QueueHandler

from codex.logger.mp_queue import LOG_QUEUE
from codex.settings.settings import LOGLEVEL


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


def get_logger(name=None, queue=LOG_QUEUE):
    """Pacify pyright."""
    logger = logging.getLogger(name)
    if len(logger.handlers) == 1:
        handler = logger.handlers[0]
        if isinstance(handler, QueueHandler) and handler.queue != queue:
            logger.handlers.clear()
    elif len(logger.handlers) > 1:
        logger.handlers.clear()
    if not logger.handlers:
        handler = CodexDjangoQueueHandler(queue)
        logger.addHandler(handler)
    logger.setLevel(LOGLEVEL)
    return logger
