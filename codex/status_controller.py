"""Librarian Status."""
from logging import DEBUG, INFO
from time import time

from django.db.models.functions.datetime import Now

from codex.librarian.notifier.tasks import LIBRARIAN_STATUS_TASK
from codex.librarian.tasks import DelayedTasks
from codex.logger_base import LoggerBaseMixin
from codex.models import LibrarianStatus


class StatusController(LoggerBaseMixin):
    """Run operations on the LibrarianStatus table."""

    _UPDATE_DELTA = 5

    def __init__(self, log_queue, librarian_queue):
        """Iinitialize logger and librarian queue."""
        self.init_logger(log_queue)
        self.librarian_queue = librarian_queue

    def _enqueue_notifier_task(self, notify=True, until=0.0):
        if not notify:
            return
        if until:
            task = DelayedTasks(until, (LIBRARIAN_STATUS_TASK,))
        else:
            task = LIBRARIAN_STATUS_TASK
        self.librarian_queue.put(task)

    def loggit(self, level, type, name, complete, total):
        """Log with a ? in place of none."""
        title = " ".join((type, name)).strip()
        complete = "?" if complete is None else complete
        total = "?" if total is None else total
        self.log.log(level, f"{title}: {complete}/{total}")

    def start(
        self,
        type,
        complete=None,
        total=None,
        name="",
        notify=True,
        now_pad=0.0,
        preactive=False,
    ):
        """Start a librarian status."""
        try:
            updates = {
                "name": name,
                "preactive": preactive,
                "complete": complete,
                "total": total,
                "active": Now() + now_pad,
                "updated_at": Now(),
            }
            LibrarianStatus.objects.filter(type=type).update(**updates)
            self._enqueue_notifier_task(notify)
            self.loggit(DEBUG, type, name, complete, total)
        except Exception as exc:
            self.log.warning(exc)

    def start_many(self, types_map):
        """Start many librarian statuses."""
        now_pad = 0.0  # a little hack to order these things
        for type, values in types_map.items():
            self.start(type, **values, notify=False, now_pad=now_pad, preactive=True)
            now_pad += 0.1
        self._enqueue_notifier_task()

    def update(self, type, complete, total, name="", notify=True, since=0.0):
        """Update a librarian status."""
        if time() - since > self._UPDATE_DELTA:
            updates = {
                "preactive": False,
                "complete": complete,
                "total": total,
                "updated_at": Now(),
            }
            try:
                LibrarianStatus.objects.filter(type=type).update(**updates)
                self._enqueue_notifier_task(notify)
                if notify:
                    self.loggit(INFO, type, name, complete, total)
                    since = time()
            except Exception as exc:
                self.log.warning(exc)
        return since

    def finish(self, type, notify=True, until=0.0):
        """Finish a librarian status."""
        try:
            updates = {**LibrarianStatus.DEFAULT_PARAMS, "updated_at": Now()}
            LibrarianStatus.objects.filter(type=type).update(**updates)
            self._enqueue_notifier_task(notify, until)
        except Exception as exc:
            self.log.warning(exc)

    def finish_many(self, types, notify=True, until=0.0):
        """Finish all librarian statuses."""
        try:
            if types:
                filter = {"type__in": types}
            else:
                filter = {}
            updates = {**LibrarianStatus.DEFAULT_PARAMS, "updated_at": Now()}
            LibrarianStatus.objects.filter(**filter).update(**updates)
            self._enqueue_notifier_task(notify, until)
            if not filter:
                self.log.info("Cleared all librarian statuses")
        except Exception as exc:
            self.log.warning(exc)
