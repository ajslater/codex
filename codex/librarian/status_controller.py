"""Librarian Status."""

from collections.abc import Iterable
from inspect import isclass
from multiprocessing import Queue
from time import time
from typing import Any

from django.db.models.functions.datetime import Now
from django.utils.timezone import datetime, now, timedelta
from loguru._logger import Logger

from codex.librarian.notifier.tasks import LIBRARIAN_STATUS_TASK
from codex.librarian.status import Status
from codex.models import LibrarianStatus


def get_default(field):
    """Get the default value for the model field."""
    return LibrarianStatus._meta.get_field(field).get_default()


DEFAULT_FIELDS = ("preactive", "complete", "total", "active", "subtitle")
STATUS_DEFAULTS = {field: get_default(field) for field in DEFAULT_FIELDS}


class StatusController:
    """Run operations on the LibrarianStatus table."""

    _UPDATE_DELTA = 5

    def __init__(self, logger_: Logger, librarian_queue: Queue):
        """Iinitialize logger and librarian queue."""
        self.log = logger_
        self.librarian_queue = librarian_queue

    def _enqueue_notifier_task(self, *, notify: bool = True):
        """Notify the status has changed."""
        if not notify:
            return
        self.librarian_queue.put(LIBRARIAN_STATUS_TASK)

    def _loggit(self, level: str, status: Status):
        """Log with a ? in place of none."""
        msg = f"{status.title()} {status.subtitle}".strip()
        msg += ": "
        if status.complete is None and status.total is None:
            msg += "In progress"
        else:
            count = "?" if status.complete is None else status.complete
            total = "?" if status.total is None else status.total
            msg += f"{count}/{total}"

        self.log.log(level, msg)

    def _update(
        self,
        status: Status,
        *,
        notify: bool,
        active: datetime | None = None,
        preactive: datetime | None = None,
    ):
        """Start a librarian status."""
        try:
            updates: dict[str, Any] = {
                "complete": status.complete,
                "total": status.total,
                "updated_at": Now(),
            }
            if preactive is not None:
                updates["preactive"] = preactive
            if active:
                updates["active"] = active
            if status.subtitle:
                updates["subtitle"] = status.subtitle
            LibrarianStatus.objects.filter(status_type=status.CODE).update(**updates)
            self._enqueue_notifier_task(notify=notify)
            self._loggit("DEBUG", status)
            status.since_updated = time()
        except Exception:
            self.log.exception(f"Update status: {status.title()}")

    def start(
        self,
        status: Status,
        *,
        notify: bool = True,
        preactive: datetime | None = None,
    ):
        """Start a librarian status."""
        status.start()
        self._update(status, notify=notify, preactive=preactive, active=now())

    def start_many(self, statii: Iterable[Status | type[Status]]):
        """Start many librarian statuses."""
        for index, status_or_class in enumerate(statii):
            status = status_or_class() if isclass(status_or_class) else status_or_class
            status.start()
            pad_ms = index * 100  # for order
            preactive = now() + timedelta(milliseconds=pad_ms)
            self._update(status, notify=False, preactive=preactive)
        self._enqueue_notifier_task(notify=True)

    def update(self, status: Status, *, notify: bool = True):
        """Update a librarian status."""
        if time() - status.since_updated < self._UPDATE_DELTA:
            # noop unless time has expired.
            return
        self._update(status, notify=notify)

    def _log_finish(self, status: Status):
        """Log finish of status with stats."""
        level = "INFO"
        suffix = ""
        if count := status.complete:
            if elapsed := status.elapsed():
                suffix = f" in {elapsed}"
            if persecond := status.per_second():
                suffix += f" at a rate of {persecond}"
        elif count == 0:
            count = "no"
            level = "DEBUG"
        if status.SINGLE or count is None:
            count = ""

        prefix_parts = (status.verbed(), str(count), status.ITEM_NAME)
        prefix = " ".join(filter(None, prefix_parts))

        if status.LOG_SUCCESS:
            level = "SUCCESS"

        self.log.log(level, f"{prefix}{suffix}.")

    def finish_many(
        self, statii: Iterable[Status | type[Status]], *, notify: bool = True
    ):
        """Finish all librarian statuses."""
        try:
            type_codes = frozenset(status.CODE for status in statii)
            ls_filter = {"status_type__in": type_codes} if type_codes else {}
            updates = {**STATUS_DEFAULTS, "updated_at": Now()}
            lses = LibrarianStatus.objects.filter(**ls_filter)
            update_ls = []
            for ls in lses.iterator():
                for key, value in updates.items():
                    setattr(ls, key, value)
                update_ls.append(ls)
            LibrarianStatus.objects.bulk_update(update_ls, tuple(updates.keys()))
            self._enqueue_notifier_task(notify=notify)
            if not ls_filter:
                self.log.info("Cleared all librarian statuses")
            for status in statii:
                if isinstance(status, Status):
                    self._log_finish(status)
        except Exception as exc:
            self.log.warning(f"Finish status {statii}: {exc}")

    def finish(self, status: Status, *, notify: bool = True):
        """Finish a librarian status."""
        try:
            self.finish_many((status,), notify=notify)
        except Exception as exc:
            self.log.warning(exc)
