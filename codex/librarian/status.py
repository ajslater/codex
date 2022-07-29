"""Librarian Status."""
from django.db.models import Q

from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.models import LibrarianStatus
from codex.notifier.tasks import LIBRARIAN_STATUS_TASK
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


def librarian_status_update(keys, complete, total, notify=True):
    """Update a librarian status."""
    if total == 0:
        return
    defaults = {**keys, "complete": complete, "total": total, "active": True}
    try:
        LibrarianStatus.objects.update_or_create(defaults=defaults, **keys)
        if notify:
            LIBRARIAN_QUEUE.put(LIBRARIAN_STATUS_TASK)
    except Exception as exc:
        LOG.warning(exc)


def librarian_status_done(keys_list, notify=True):
    """Finish a librarian status."""
    filter = Q()
    for keys in keys_list:
        filter |= Q(**keys)
    try:
        LibrarianStatus.objects.filter(filter).update(
            active=False, complete=0, total=None
        )
        if notify:
            LIBRARIAN_QUEUE.put(LIBRARIAN_STATUS_TASK)
        if filter == Q():
            LOG.info("Cleared all librarian statuses")
    except Exception as exc:
        LOG.warning(exc)
