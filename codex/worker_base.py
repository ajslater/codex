"""General worker class inherits queues."""

from multiprocessing.queues import Queue

from loguru._logger import Logger
from typing_extensions import override

from codex.status_controller import StatusController


class WorkerBaseBaseMixin:
    """Mixin for inheriting queues."""

    def init_worker(self, logger_: Logger | None, librarian_queue: Queue | None):
        """Initialize queues."""
        if not logger_ or not librarian_queue:
            reason = f"logger and librarian queue must be passed in {logger_=} {librarian_queue=}"
            raise ValueError(reason)
        self.log = logger_  # pyright: ignore[reportUninitializedInstanceVariable]
        self.librarian_queue = librarian_queue  # pyright: ignore[reportUninitializedInstanceVariable]


class WorkerBaseMixin(WorkerBaseBaseMixin):
    """Worker mixin also sets up status controller."""

    @override
    def init_worker(self, logger_, librarian_queue: Queue | None):
        super().init_worker(logger_, librarian_queue)
        if logger_ and librarian_queue:
            self.status_controller = StatusController(  # pyright: ignore[reportUninitializedInstanceVariable]
                logger_, librarian_queue
            )
