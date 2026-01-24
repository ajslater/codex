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

    @staticmethod
    def _finish_status_prepare(
        positive_statii: MappingProxyType[str, Status | type[Status]],
        updates: dict[str, Any],
    ):
        # Filter all active or preactive statii
        ls_filter = Q(active__isnull=False) | Q(preactive__isnull=False)
        if positive_statii:
            ls_filter_dict: dict[str, Any] = {"status_type__in": positive_statii.keys()}
            # Filter on status codes
            ls_filter &= Q(**ls_filter_dict)
        lses = LibrarianStatus.objects.filter(ls_filter)
        update_ls = []
        log_statii = []
        for ls in lses.iterator():
            for key, value in updates.items():
                setattr(ls, key, value)
            update_ls.append(ls)
            status = positive_statii.get(ls.status_type)
            if isinstance(status, Status):
                log_statii.append(status)
        return update_ls, log_statii

    def _log_finish(self, status: Status, *, clear_subtitle: bool):
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

        if clear_subtitle:
            status.subtitle = ""

        prefix_parts = filter(
            None, (status.verbed(), count, status.ITEM_NAME, status.subtitle)
        )
        prefix = " ".join(prefix_parts)

        self.log.log(level, f"{prefix}{suffix}.")

    def finish_many(
        self,
        statii: Iterable[Status | type[Status] | None],
        *,
        notify: bool = True,
        clear_subtitle=True,
    ):
        """Finish all librarian statuses."""
        positive_statii: MappingProxyType[str, Status | type[Status]] = (
            MappingProxyType({status.CODE: status for status in statii if status})
        )
        try:
            if statii and not positive_statii:
                # if statii has elements but they were all None, this is a noop.
                # But if statii was empty this is a finish all command.
                return
            updates = {**STATUS_DEFAULTS, "updated_at": Now()}
            update_ls, log_statii = self._finish_status_prepare(
                positive_statii, updates
            )
            LibrarianStatus.objects.bulk_update(update_ls, tuple(updates.keys()))
            self._enqueue_notifier_task(notify=notify)
            if not positive_statii:
                self.log.info("Cleared all librarian statuses")
            for status in log_statii:
                self._log_finish(status, clear_subtitle=clear_subtitle)
        except Exception:
            self.log.exception(f"Finish status {positive_statii}")

    def finish(
        self, status: Status | None, *, notify: bool = True, clear_subtitle=True
    ):
        """Finish a librarian status."""
        try:
            self.finish_many((status,), notify=notify, clear_subtitle=clear_subtitle)
        except Exception as exc:
            self.log.warning(exc)
