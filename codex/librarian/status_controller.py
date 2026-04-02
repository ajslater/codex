"""Librarian Status."""

from collections.abc import Iterable
from inspect import isclass
from multiprocessing import Queue
from time import time
from types import MappingProxyType
from typing import Any

from django.db.models.functions.datetime import Now
from django.db.models.query import Q
from django.utils.timezone import datetime, now, timedelta
from loguru._logger import Logger

from codex.librarian.notifier.tasks import LIBRARIAN_STATUS_TASK
from codex.librarian.status import Status
from codex.models.admin import LibrarianStatus


def get_default(field):
    """Get the default value for the model field."""
    return LibrarianStatus._meta.get_field(field).get_default()


DEFAULT_FIELDS = ("preactive", "complete", "total", "active", "subtitle")
STATUS_DEFAULTS = {field: get_default(field) for field in DEFAULT_FIELDS}


class StatusController:
    """Run operations on the LibrarianStatus table."""

    _UPDATE_DELTA = 5

    def __init__(self, logger_: Logger, librarian_queue: Queue) -> None:
        """Iinitialize logger and librarian queue."""
        self.log = logger_
        self.librarian_queue = librarian_queue

    def _enqueue_notifier_task(self, *, notify: bool = True) -> None:
        """Notify the status has changed."""
        if not notify:
            return
        self.librarian_queue.put(LIBRARIAN_STATUS_TASK)

    def _loggit(self, level: str, status: Status) -> None:
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
    ) -> None:
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
    ) -> None:
        """Start a librarian status."""
        status.start()
        self._update(status, notify=notify, preactive=preactive, active=now())

    def start_many(self, statii: Iterable[Status | type[Status]]) -> None:
        """Start many librarian statuses."""
        for index, status_or_class in enumerate(statii):
            status = status_or_class() if isclass(status_or_class) else status_or_class
            status.start()
            pad_ms = index * 100  # for order
            preactive = now() + timedelta(milliseconds=pad_ms)
            self._update(status, notify=False, preactive=preactive)
        self._enqueue_notifier_task(notify=True)

    def update(self, status: Status, *, notify: bool = True) -> None:
        """Update a librarian status."""
        if time() - status.since_updated < self._UPDATE_DELTA:
            # noop unless time has expired.
            return
        self._update(status, notify=notify)

    def _log_finish(self, status: Status) -> None:
        """Log finish of status with stats."""
        level = "INFO"
        suffix = ""
        if elapsed := status.elapsed():
            suffix += f" in {elapsed}"
        if status.SINGLE:
            count = ""
        elif count := status.complete:
            count = str(count)
            if persecond := status.per_second():
                suffix += f" at a rate of {persecond}"
        else:
            count = "no"
            level = "DEBUG"

        if status.log_success:
            level = "SUCCESS"

        prefix_parts = filter(
            None, (status.verbed(), count, status.ITEM_NAME, status.subtitle)
        )
        prefix = " ".join(prefix_parts)

        self.log.log(level, f"{prefix}{suffix}.")

    def _finish_many_log(self, updated_statii, *, is_positive_statii: bool):
        """Log when done."""
        if is_positive_statii:
            for status in updated_statii:
                if isinstance(status, Status):
                    self._log_finish(status)
        else:
            self.log.info("Cleared all librarian statuses")

    def finish_many(
        self,
        statii: Iterable[Status | type[Status] | None],
        *,
        notify: bool = True,
    ) -> None:
        """Finish all librarian statuses."""
        positive_statii: MappingProxyType[str, Status | type[Status]] = (
            MappingProxyType({status.CODE: status for status in statii if status})
        )
        try:
            # Construct update query
            if statii and not positive_statii:
                # if statii has elements but they were all None, this is a noop.
                # But if statii was empty this is a finish all command.
                # This fires an extra LIBRARIAN_STATUS notification if none. idk if that's appropriate.
                return
            updates = {**STATUS_DEFAULTS, "updated_at": Now()}
            if positive_statii:
                # Finish specific statuses unconditionally by status_type.
                # Don't require active/preactive to be set — subtasks may
                # have already been individually finished.
                ls_filter = Q(status_type__in=positive_statii.keys())
            else:
                # Clear-all: only touch rows that are currently active.
                ls_filter = Q(active__isnull=False) | Q(preactive__isnull=False)

            # Perform updates
            update_statii = LibrarianStatus.objects.filter(ls_filter)
            # Save statii for individual reporting.
            updated_statii = update_statii.values()
            update_statii.update(**updates)

            self._finish_many_log(
                updated_statii, is_positive_statii=bool(positive_statii)
            )
        except Exception:
            self.log.exception(f"Finish status {positive_statii}")
        finally:
            self._enqueue_notifier_task(notify=notify)

    def finish(self, status: Status | None, *, notify: bool = True) -> None:
        """Finish a librarian status."""
        try:
            self.finish_many((status,), notify=notify)
        except Exception as exc:
            self.log.warning(exc)
