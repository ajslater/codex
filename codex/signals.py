"""Signal actions."""

import signal

from asyncio import Event

from django.core.cache import cache
from django.db.backends.signals import connection_created
from django.db.models.signals import m2m_changed

from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    BroadcastNotifierTask,
    DelayedTasks,
)
from codex.settings.logging import get_logger


LOG = get_logger(__name__)
SIGNAL_NAMES = {"SIGINT", "SIGTERM", "SIGBREAK"}
RESTART_EVENT = Event()
SHUTDOWN_EVENT = Event()


def _shutdown_signal_handler():
    global SHUTDOWN_EVENT
    if SHUTDOWN_EVENT.is_set():
        return
    LOG.info("Asking hypercorn to shut down gracefully. Could take 10 seconds...")
    SHUTDOWN_EVENT.set()


def _restart_signal_handler():
    global RESTART_EVENT
    if RESTART_EVENT.is_set():
        return
    LOG.info("Restart signal received.")
    RESTART_EVENT.set()
    _shutdown_signal_handler()


def bind_signals(loop):
    """Binds signals to the handlers."""
    for signal_name in SIGNAL_NAMES:
        sig = getattr(signal, signal_name, None)
        if sig:
            loop.add_signal_handler(sig, _shutdown_signal_handler)
    loop.add_signal_handler(signal.SIGUSR1, _restart_signal_handler)


def _activate_wal_journal(sender, connection, **kwargs):  # noqa: F841
    """Enable sqlite WAL journal."""
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=wal;")
        LOG.debug("sqlite journal_mode=wal")


def _user_group_change(action, instance, pk_set, model, **kwargs):  # noqa: F841
    """Clear cache and send update signals when groups change."""
    if model.__name__ == "Group" and action in (
        "post_add",
        "post_remove",
        "post_clear",
    ):
        cache.clear()
        tasks = (BroadcastNotifierTask("LIBRARY_CHANGED"),)
        task = DelayedTasks(2, tasks)
        LIBRARIAN_QUEUE.put(task)


def connect_signals():
    """Connect actions to signals."""
    connection_created.connect(_activate_wal_journal)
    m2m_changed.connect(_user_group_change)
