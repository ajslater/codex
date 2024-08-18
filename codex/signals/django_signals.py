"""Django signal actions."""

from time import time

import sqlite_regex
from django.core.cache import cache
from django.db.backends.signals import connection_created
from django.db.models.signals import m2m_changed

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import LIBRARIAN_STATUS_TASK
from codex.librarian.tasks import DelayedTasks
from codex.logger.logging import get_logger

GROUP_CHANGE_MODEL_NAMES = frozenset(("User", "Library"))
GROUP_CHANGE_ACTIONS = frozenset(
    {
        "post_add",
        "post_remove",
        "post_clear",
    }
)
LOG = get_logger(__name__)


def _load_regex_extension(**kwargs):
    """Load the sqlite-regexp extension."""
    path = sqlite_regex.loadable_path()
    try:
        conn = kwargs["connection"].connection
        conn.enable_load_extension(True)
        conn.load_extension(path)
    except Exception as exc:
        LOG.warning(f"Unable to load sqlite-regex extension: {exc}. Tried with {path}")


def _db_connect(**kwargs):
    _load_regex_extension(**kwargs)


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


# def _cache_invalidated(sender, **kwargs):
#    """For cache debugging."""
#    print(f"invalidated signal {sender}")


def connect_signals():
    """Connect actions to signals."""
    connection_created.connect(_db_connect)
    m2m_changed.connect(_user_group_change)
    # post_invalidation.connect(_cache_invalidated)
