"""Librarian Status."""
from dataclasses import dataclass

from django.db.models.functions.datetime import Now

from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.models import LibrarianStatus
from codex.notifier.tasks import LIBRARIAN_STATUS_TASK
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


@dataclass
class StatusControlFinishTask:
    """Finish a status task."""

    type: str
    notify: bool = True


class StatusControl:
    """Run operations on the LibrarianStatus table."""

    @staticmethod
    def start(
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
                LIBRARIAN_QUEUE.put(LIBRARIAN_STATUS_TASK)
        except Exception as exc:
            LOG.warning(exc)

    @classmethod
    def start_many(cls, types_map):
        """Start many librarian statuses."""
        now_pad = 0.0  # a little hack to order these things
        for type, values in types_map.items():
            cls.start(type, **values, notify=False, now_pad=now_pad, preactive=True)
            now_pad += 0.1
        LIBRARIAN_QUEUE.put(LIBRARIAN_STATUS_TASK)

    @staticmethod
    def update(type, complete, total, notify=True):
        """Update a librarian status."""
        updates = {
            "preactive": False,
            "complete": complete,
            "total": total,
            "updated_at": Now(),
        }
        try:
            LibrarianStatus.objects.filter(type=type).update(**updates)
            if notify:
                LIBRARIAN_QUEUE.put(LIBRARIAN_STATUS_TASK)
        except Exception as exc:
            LOG.warning(exc)

    @staticmethod
    def finish(type, notify=True):
        """Finish a librarian status."""
        try:
            updates = {**LibrarianStatus.DEFAULT_PARAMS, "updated_at": Now()}
            LibrarianStatus.objects.filter(type=type).update(**updates)
            if notify:
                LIBRARIAN_QUEUE.put(LIBRARIAN_STATUS_TASK)
        except Exception as exc:
            LOG.warning(exc)

    @staticmethod
    def finish_many(types, notify=True):
        """Finish all librarian statuses."""
        try:
            if types:
                filter = {"type__in": types}
            else:
                filter = {}
            updates = {**LibrarianStatus.DEFAULT_PARAMS, "updated_at": Now()}
            LibrarianStatus.objects.filter(**filter).update(**updates)
            if notify:
                LIBRARIAN_QUEUE.put(LIBRARIAN_STATUS_TASK)
            if not filter:
                LOG.info("Cleared all librarian statuses")
        except Exception as exc:
            LOG.warning(exc)
