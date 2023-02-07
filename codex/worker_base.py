"""General worker class inherits queues."""
from codex.librarian.status_controller import StatusController
from codex.logger_base import LoggerBaseMixin


class WorkerBaseMixin(LoggerBaseMixin):
    """General worker class for inheriting queues."""

    def init_worker(self, log_queue, librarian_queue):
        """Initialize queues."""
        if log_queue is None or librarian_queue is None:
            raise ValueError(
                f"{self.__class__.__name__} initialization "
                f"missing {log_queue=} or {librarian_queue=}"
            )
        self.init_logger(log_queue)
        self.librarian_queue = librarian_queue
        self.status_controller = StatusController(log_queue, librarian_queue)
