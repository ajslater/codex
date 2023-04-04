"""Django signal actions."""
from time import time

from django.core.cache import cache
from django.db.backends.signals import connection_created
from django.db.models.signals import m2m_changed

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import LIBRARIAN_STATUS_TASK
from codex.librarian.tasks import DelayedTasks
from codex.logger.logging import get_logger

GROUP_CHANGE_MODEL_NAMES = frozenset(("User", "Library"))
GROUP_CHANGE_ACTIONS = frozenset(
    (
        "post_add",
        "post_remove",
        "post_clear",
    )
)


def _activate_wal_journal(**kwargs):
    """Enable sqlite WAL journal."""
    connection = kwargs["connection"]
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=wal;")


def _user_group_change(**kwargs):
    """Clear cache and send update signals when groups change."""
    model = kwargs["model"]
    action = kwargs["action"]
    if (
        model.__name__ not in GROUP_CHANGE_MODEL_NAMES
        or action not in GROUP_CHANGE_ACTIONS
    ):
        return
    cache.clear()
    tasks = (LIBRARIAN_STATUS_TASK,)
    task = DelayedTasks(time() + 2, tasks)
    LIBRARIAN_QUEUE.put(task)


def connect_signals():
    """Connect actions to signals."""
    logger = get_logger(__name__)
    connection_created.connect(_activate_wal_journal)
    logger.debug("sqlite journal_mode=wal")
    m2m_changed.connect(_user_group_change)
