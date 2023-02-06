"""Class to run librarian tasks inline without a thread."""
from codex.settings.logging import get_logger


class LoggerBase:
    """A class that holds it's own logger."""

    def init_logger(self, log_queue):
        """Set up logger."""
        name = getattr(self, "NAME", self.__class__.__name__)
        self.logger = get_logger(name, log_queue)
