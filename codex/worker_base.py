"""General worker class inherits queues."""
from multiprocessing import Queue

from codex.librarian.status_controller import StatusController
from codex.logger_base import LoggerBaseMixin


class WorkerBaseMixin(LoggerBaseMixin):
    """General worker class for inheriting queues."""

    def init_worker(self, log_queue: Queue, librarian_queue: Queue):
        """Initialize queues."""
        self.init_logger(log_queue)
        self.librarian_queue = librarian_queue
        self.status_controller = StatusController(log_queue, librarian_queue)
