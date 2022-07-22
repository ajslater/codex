"""Librarian Status."""
from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.models import LibrarianStatus
from codex.notifier.tasks import LIBRARIAN_STATUS_TASK


def librarian_status_update(keys, complete, total, notify=True):
    """Update a librarian status."""
    if total == 0:
        return
    defaults = {**keys, "complete": complete, "total": total, "active": True}
    LibrarianStatus.objects.update_or_create(defaults=defaults, **keys)
    if notify:
        LIBRARIAN_QUEUE.put(LIBRARIAN_STATUS_TASK)


def librarian_status_done(keys, notify=True):
    """Finish a librarian status."""
    LibrarianStatus.objects.filter(**keys).update(active=False, complete=0, total=None)
    if notify:
        LIBRARIAN_QUEUE.put(LIBRARIAN_STATUS_TASK)
