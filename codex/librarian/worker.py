"""Mixin for common librarian thread attributes."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from codex.librarian.status_controller import StatusController

if TYPE_CHECKING:
    # Type-hint-only — runtime imports stay lean across the nine
    # librarian modules that import this chain.
    from multiprocessing.queues import Queue

    from loguru._logger import Logger


class WorkerMixin:
    """Mixin for common thread attributes."""

    def init_worker(
        self, /, logger_: Logger, librarian_queue: Queue, db_write_lock
    ) -> None:
        """Initialize queues."""
        if not all((logger_, librarian_queue, db_write_lock)):
            reason = f"{logger_=}, {librarian_queue=}, and {db_write_lock=} must be passed in."
            raise ValueError(reason)
        self.log = logger_  # pyright: ignore[reportUninitializedInstanceVariable]
        self.librarian_queue = librarian_queue  # pyright: ignore[reportUninitializedInstanceVariable]
        self.db_write_lock = db_write_lock  # pyright: ignore[reportUninitializedInstanceVariable]


class WorkerStatusMixin(WorkerMixin):
    """Worker mixin also sets up status controller."""

    @override
    def init_worker(self, /, logger_, librarian_queue: Queue, db_write_lock) -> None:
        super().init_worker(logger_, librarian_queue, db_write_lock)
        self.status_controller = StatusController(  # pyright: ignore[reportUninitializedInstanceVariable]
            logger_, librarian_queue
        )


class WorkerBase(WorkerMixin):
    """Base for Worker."""

    def __init__(self, logger_, librarian_queue: Queue, db_write_lock) -> None:
        """Initialize Worker."""
        super().__init__()
        self.init_worker(logger_, librarian_queue, db_write_lock)


class WorkerStatusBase(WorkerStatusMixin):
    """Base for Status Worker."""

    def __init__(self, logger_, librarian_queue: Queue, db_write_lock) -> None:
        """Initialize Worker."""
        super().__init__()
        self.init_worker(logger_, librarian_queue, db_write_lock)


class WorkerStatusAbortableBase(WorkerStatusBase):
    """Base for Abortable Status Worker."""

    def __init__(self, logger_, librarian_queue: Queue, db_write_lock, event) -> None:
        """Initialize Abortable Worker."""
        super().__init__(logger_, librarian_queue, db_write_lock)
        self.abort_event = event
