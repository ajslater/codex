"""
Shared pieces of the pending-delete revival.

Clearing a stamp is a bare ``.update()`` outside any import, so nothing
clears the caches or tells a client on its own. Both the poller's
automatic revival and the admin's manual one need the same follow-up,
so it lives here rather than being written twice and drifting.
"""

from collections.abc import Iterable
from datetime import timedelta
from typing import Final

from django.core.cache import cache
from django.db.models.functions import Now

from codex.librarian.covers.tasks import CoverCreateTask, CoverRemoveTask
from codex.librarian.notifier.tasks import (
    LIBRARY_CHANGED_TASK,
    PENDING_DELETES_CHANGED_TASK,
)
from codex.models import Comic, Folder

#: How long a row that vanished from disk is kept before it is really
#: deleted. A safety delay before an irreversible action, not a tuning
#: knob -- the same shape as the telemeter's opt-out window, which is
#: documented to admins in prose while still not being configurable.
#: The effective window is this plus the time to the next nightly run.
PENDING_DELETE_WINDOW: Final = timedelta(hours=24)


def clear_stamps(model, **filter_kwargs) -> int:
    """
    Clear the pending-delete stamp.

    Never ``.save()``: ``WatchedPath.presave`` stats the path, which
    raises ``FileNotFoundError`` for a row that is still missing -- and
    an admin can revive one of those deliberately. ``updated_at`` is
    written explicitly because ``auto_now`` does not fire on a queryset
    ``.update()``.
    """
    return model.objects.filter(missing_since__isnull=False, **filter_kwargs).update(
        missing_since=None, updated_at=Now()
    )


def publish_revival(librarian_queue, comic_pks: Iterable[int]) -> None:
    """
    Make a revival visible to clients.

    Without this the row comes back in the database and stays invisible
    in the browser until some unrelated import happens to run.
    """
    pks = frozenset(comic_pks)
    if pks:
        # A cover that failed to render while the file was missing left
        # a permanent zero-byte sentinel that ``_filter_pending_pks``
        # treats as present and never retries, so the comic would come
        # back with a permanently blank cover. Remove, then recreate.
        librarian_queue.put(CoverRemoveTask(pks, custom=False))
        librarian_queue.put(CoverCreateTask(tuple(pks), custom=False))
    cache.clear()
    librarian_queue.put(LIBRARY_CHANGED_TASK)
    librarian_queue.put(PENDING_DELETES_CHANGED_TASK)


def pending_delete_counts() -> dict[str, int]:
    """Count rows currently held by the retention window."""
    return {
        "comics": Comic.objects.filter(missing_since__isnull=False).count(),
        "folders": Folder.objects.filter(missing_since__isnull=False).count(),
    }
