"""General worker class inherits queues."""

from multiprocessing import Queue

from codex.logger_base import LoggerBaseMixin
from codex.status_controller import StatusController


class WorkerBaseMixin(LoggerBaseMixin):
    """General worker class for inheriting queues."""

    def init_worker(self, log_queue: Queue, librarian_queue: Queue):
        """Initialize queues."""
        self.init_logger(log_queue)
        self.librarian_queue = librarian_queue  # pyright: ignore[reportUninitializedInstanceVariable]
        self.status_controller = StatusController(  # pyright: ignore[reportUninitializedInstanceVariable]
            log_queue, librarian_queue
        )
