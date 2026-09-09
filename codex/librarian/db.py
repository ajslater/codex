"""Per-process database connection policy."""

from django.db import DEFAULT_DB_ALIAS, connections

from codex.settings import LIBRARIAN_CONN_MAX_AGE


def enable_persistent_connections(
    max_age: int | None = LIBRARIAN_CONN_MAX_AGE, *, alias: str = DEFAULT_DB_ALIAS
) -> None:
    """
    Turn on persistent Django connections for the *calling process*.

    ``DATABASES`` ships with Django's default ``CONN_MAX_AGE=0`` because
    an ASGI request's worker thread is retired when the request ends, so
    a connection kept open past ``request_finished`` is orphaned rather
    than reused (see ``codex.settings``). Threads that genuinely outlive
    a unit of work — the librarian's queue workers, and the HTTP worker
    pool when it is enabled — are the opposite case: reusing a
    connection saves them a SQLite open per task, most of which is
    SQLite re-parsing the schema.

    ``connections.settings[alias]`` is the very dict every
    ``DatabaseWrapper`` for that alias holds as ``settings_dict`` and
    re-reads ``CONN_MAX_AGE`` from on each ``connect()``, so this
    applies to wrappers created later on any thread, and to an existing
    wrapper the next time it reconnects. It is process-local state and
    cannot leak to another process.

    Call it before the threads that should benefit exist. Never call it
    for a process whose only DB work is per-request on throwaway
    threads.
    """
    connections.settings[alias]["CONN_MAX_AGE"] = max_age
