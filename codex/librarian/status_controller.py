"""Librarian Status."""
from datetime import datetime, timedelta

from django.db.models.functions.datetime import Now

from codex.logger_base import LoggerBaseMixin
from codex.models import LibrarianStatus
from codex.notifier.tasks import LIBRARIAN_STATUS_TASK


class StatusController(LoggerBaseMixin):
    """Run operations on the LibrarianStatus table."""

    _UPDATE_DELTA = timedelta(seconds=5)

    def __init__(self, log_queue, librarian_queue):
        """Iinitialize logger and librarian queue."""
        self.init_logger(log_queue)
        self.librarian_queue = librarian_queue

    def start(
        self,
        type,
        total=0,
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
                "complete": 0,
                "total": total,
                "active": Now() + now_pad,
                "updated_at": Now(),
            }
            LibrarianStatus.objects.filter(type=type).update(**updates)
            if notify:
                self.librarian_queue.put(LIBRARIAN_STATUS_TASK)
        except Exception as exc:
            self.logger.warning(exc)

    def start_many(self, types_map):
        """Start many librarian statuses."""
        now_pad = 0.0  # a little hack to order these things
        for type, values in types_map.items():
            self.start(type, **values, notify=False, now_pad=now_pad, preactive=True)
            now_pad += 0.1
        self.librarian_queue.put(LIBRARIAN_STATUS_TASK)

    def update(self, type, complete, total, name="", notify=True, since=None):
        """Update a librarian status."""
        if since is None or (datetime.now() - since) > self.UPDATE_DELTA:
            updates = {
                "preactive": False,
                "complete": complete,
                "total": total,
                "updated_at": Now(),
            }
            try:
                LibrarianStatus.objects.filter(type=type).update(**updates)
                if notify:
                    self.librarian_queue.put(LIBRARIAN_STATUS_TASK)
                    since = datetime.now()
                    title = " ".join((type, name)).strip()
                    self.logger.info(f"{title}: {complete}/{total}")
            except Exception as exc:
                self.logger.warning(exc)
        return since

    def finish(self, type, notify=True):
        """Finish a librarian status."""
        try:
            updates = {**LibrarianStatus.DEFAULT_PARAMS, "updated_at": Now()}
            LibrarianStatus.objects.filter(type=type).update(**updates)
            if notify:
                self.librarian_queue.put(LIBRARIAN_STATUS_TASK)
        except Exception as exc:
            self.logger.warning(exc)

    def finish_many(self, types, notify=True):
        """Finish all librarian statuses."""
        try:
            if types:
                filter = {"type__in": types}
            else:
                filter = {}
            updates = {**LibrarianStatus.DEFAULT_PARAMS, "updated_at": Now()}
            LibrarianStatus.objects.filter(**filter).update(**updates)
            if notify:
                self.librarian_queue.put(LIBRARIAN_STATUS_TASK)
            if not filter:
                self.logger.info("Cleared all librarian statuses")
        except Exception as exc:
            self.logger.warning(exc)
