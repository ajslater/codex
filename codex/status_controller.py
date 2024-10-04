"""Librarian Status."""

from enum import Enum
from logging import DEBUG, INFO
from time import time

from django.db.models.functions.datetime import Now

from codex.choices import ADMIN_STATUS_TITLES
from codex.librarian.notifier.tasks import LIBRARIAN_STATUS_TASK
from codex.librarian.tasks import DelayedTasks
from codex.logger_base import LoggerBaseMixin
from codex.models import LibrarianStatus
from codex.status import Status


def get_default(field):
    """Get the default value for the model field."""
    return LibrarianStatus._meta.get_field(field).get_default()


DEFAULT_FIELDS = ("preactive", "complete", "total", "active", "subtitle")
STATUS_DEFAULTS = {field: get_default(field) for field in DEFAULT_FIELDS}


class StatusController(LoggerBaseMixin):
    """Run operations on the LibrarianStatus table."""

    _UPDATE_DELTA = 5

    def __init__(self, log_queue, librarian_queue):
        """Iinitialize logger and librarian queue."""
        self.init_logger(log_queue)
        self.librarian_queue = librarian_queue

    def _enqueue_notifier_task(self, notify=True, until=0.0):
        """Notify the status has changed."""
        if not notify:
            return
        if until:
            task = DelayedTasks(until, (LIBRARIAN_STATUS_TASK,))
        else:
            task = LIBRARIAN_STATUS_TASK
        self.librarian_queue.put(task)

    def _loggit(self, level, status):
        """Log with a ? in place of none."""
        type_title = ADMIN_STATUS_TITLES[status.status_type]
        msg = " ".join((type_title, status.subtitle)).strip()
        msg += ": "
        if status.complete is None and status.total is None:
            msg += "In progress"
        else:
            count = "?" if status.complete is None else status.complete
            total = "?" if status.total is None else status.total
            msg += f"{count}/{total}"

        self.log.log(level, msg)

    @staticmethod
    def _to_status_type_value(status):
        """Convert Status and Enums to str types."""
        if isinstance(status, Status):
            status = status.status_type
        elif isinstance(status, Enum):
            status = status.value
        return status

    def start(
        self,
        status,
        notify=True,
        now_pad=0.0,
        preactive=False,
    ):
        """Start a librarian status."""
        try:
            if not status.status_type:
                reason = f"Bad status type: {status.status_type}"
                raise ValueError(reason)  # noqa: TRY301
            updates = {
                "preactive": preactive,
                "complete": status.complete,
                "total": status.total,
                "active": Now() + now_pad,
                "subtitle": status.subtitle,
                "updated_at": Now(),
            }
            LibrarianStatus.objects.filter(status_type=status.status_type).update(
                **updates
            )
            self._enqueue_notifier_task(notify)
            self._loggit(DEBUG, status)
            status.since = time()
        except Exception:
            title = ADMIN_STATUS_TITLES[status.status_type]
            self.log.exception(f"Start status: {title}")

    def start_many(self, status_iterable):
        """Start many librarian statuses."""
        now_pad = 0.0  # a little hack to order these things
        for status in status_iterable:
            self.start(status, notify=False, now_pad=now_pad, preactive=True)
            now_pad += 0.1
        self._enqueue_notifier_task()

    def update(self, status, notify=True):
        """Update a librarian status."""
        if time() - status.since < self._UPDATE_DELTA:
            # noop unless time has expired.
            return
        updates = {
            "preactive": False,
            "complete": status.complete,
            "total": status.total,
            "updated_at": Now(),
        }
        try:
            LibrarianStatus.objects.filter(status_type=status.status_type).update(
                **updates
            )
            self._enqueue_notifier_task(notify)
            if notify:
                self._loggit(INFO, status)
                status.since = time()
        except Exception as exc:
            title = ADMIN_STATUS_TITLES[status.status_type]
            self.log.warning(f"Update status {title}: {exc}")

    def finish_many(self, statii, notify=True, until=0.0):
        """Finish all librarian statuses."""
        try:
            types = []
            for status in statii:
                types += [self._to_status_type_value(status)]
            ls_filter = {"status_type__in": types} if types else {}
            updates = {**STATUS_DEFAULTS, "updated_at": Now()}
            lses = LibrarianStatus.objects.filter(**ls_filter)
            update_ls = []
            for ls in lses.iterator():
                for key, value in updates.items():
                    setattr(ls, key, value)
                update_ls.append(ls)
            LibrarianStatus.objects.bulk_update(update_ls, tuple(updates.keys()))
            self._enqueue_notifier_task(notify, until)
            if ls_filter:
                # self.log.debug(f"Cleared {types} librarian statuses")
                pass
            else:
                self.log.info("Cleared all librarian statuses")
        except Exception as exc:
            self.log.warning(f"Finish status {statii}: {exc}")

    def finish(self, status, notify=True, until=0.0):
        """Finish a librarian status."""
        try:
            self.finish_many((status,), notify=notify, until=until)
        except Exception as exc:
            self.log.warning(exc)
