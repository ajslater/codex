"""Class to run librarian tasks inline without a thread."""

from codex.logger.logging import get_logger


class LoggerBaseMixin:
    """A class that holds it's own logger."""

    def init_logger(self, log_queue):
        """Set up logger."""
        self.log_queue = log_queue
        self.log = get_logger(self.__class__.__name__, log_queue)
