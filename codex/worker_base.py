"""General worker class inherits queues."""

from codex.logger_base import LoggerBaseMixin
from codex.status_controller import StatusController


class WorkerBaseMixin(LoggerBaseMixin):
    """General worker class for inheriting queues."""

    def init_worker(self, log_queue, librarian_queue):
        """Initialize queues."""
        self.init_logger(log_queue)
        self.librarian_queue = librarian_queue
        self.status_controller = StatusController(log_queue, librarian_queue)
