"""Logging classes."""
import logging

from logging.handlers import QueueHandler
from os import environ

from codex.logger.log_queue import LOG_QUEUE
from codex.settings.settings import LOGLEVEL


LOG_TO_CONSOLE = environ.get("CODEX_LOG_TO_CONSOLE") != "0"
LOG_TO_FILE = environ.get("CODEX_LOG_TO_FILE") != "0"


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
    handler = CodexDjangoQueueHandler(queue)
    logger.addHandler(handler)
    logger.setLevel(LOGLEVEL)
    return logger


# TODO move to codex/logger
