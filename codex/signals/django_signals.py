"""Django signal actions."""
from time import time

from django.core.cache import cache
from django.db.backends.signals import connection_created
from django.db.models.signals import m2m_changed

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import LIBRARIAN_STATUS_TASK
from codex.librarian.tasks import DelayedTasks
from codex.logger.logging import get_logger


def _activate_wal_journal(sender, connection, **kwargs):  # noqa: F841
    """Enable sqlite WAL journal."""
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=wal;")


def _user_group_change(action, instance, pk_set, model, **kwargs):  # noqa: F841
    """Clear cache and send update signals when groups change."""
    if model.__name__ != "Group" or action not in (
        "post_add",
        "post_remove",
        "post_clear",
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
