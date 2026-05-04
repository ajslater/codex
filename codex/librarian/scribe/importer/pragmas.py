"""
SQLite PRAGMA overrides scoped to a bulk-import run.

The steady-state PRAGMAs in ``codex/settings/__init__.py`` are tuned
for concurrent readers plus a slow-drip writer. A bulk import
inverts that balance: the writer dominates and reader concurrency is
irrelevant for the run's duration.

The override here:

* bumps the page cache aggressively (the 600k-comic working set fits
  inside it, eliminating page-cache misses across the link-phase
  prune walk), and
* defers WAL checkpoints until import finish (the default 1000-page
  autocheckpoint fires hundreds of times per large import; each one
  briefly stalls the writer).

A ``connection_created`` signal handler re-applies the override on
any connection Django opens during the import — Django recycles
connections via ``CONN_MAX_AGE``, so without the signal a long-
running import would silently lose the override mid-run.

On exit, the steady-state values are restored, the WAL is
force-checkpointed (otherwise it would carry the import's worth of
deferred frames forever), and ``PRAGMA optimize`` is fired so the
query planner uses fresh statistics post-import.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from django.db import connection
from django.db.backends.signals import connection_created

from codex.settings import IMPORTER_SQLITE_CACHE_KB

if TYPE_CHECKING:
    from collections.abc import Generator

# Steady-state SQLite cache; must match the value embedded in
# ``settings/__init__.py``'s ``_SQLITE_PRAGMAS`` so the restore
# returns the connection to its default behavior.
_STEADY_STATE_CACHE_KB = 64000
# Default ``wal_autocheckpoint`` per SQLite's docs.
_STEADY_STATE_WAL_AUTOCHECKPOINT = 1000


def _importer_pragmas() -> tuple[str, ...]:
    """
    Build the importer-scoped PRAGMA list.

    Resolved at call time so the cache size honors a config-file
    change between imports without a daemon restart.
    """
    return (
        f"PRAGMA cache_size=-{IMPORTER_SQLITE_CACHE_KB}",
        "PRAGMA wal_autocheckpoint=0",
    )


_RESTORE_PRAGMAS = (
    f"PRAGMA cache_size=-{_STEADY_STATE_CACHE_KB}",
    f"PRAGMA wal_autocheckpoint={_STEADY_STATE_WAL_AUTOCHECKPOINT}",
)


def _apply_pragmas(conn, pragmas: tuple[str, ...]) -> None:
    """Run a sequence of PRAGMA statements on ``conn``."""
    with conn.cursor() as cursor:
        for pragma in pragmas:
            cursor.execute(pragma)


def _on_connection_created(
    sender,  # noqa: ARG001
    connection,
    **_kwargs,
) -> None:
    """
    Re-apply importer PRAGMAs to a freshly opened connection.

    The signal passes the new connection as the ``connection`` arg.
    Use it directly so we don't depend on which thread-local Django
    has currently bound to the module-level ``connection`` proxy.
    """
    _apply_pragmas(connection, _importer_pragmas())


@contextmanager
def importer_pragmas() -> Generator[None]:
    """
    Apply importer PRAGMAs for the duration of an import.

    Yields with the override in place. On exit, restores steady-state
    values, force-checkpoints the WAL, and runs ``PRAGMA optimize``.
    """
    connection_created.connect(_on_connection_created)
    _apply_pragmas(connection, _importer_pragmas())
    try:
        yield
    finally:
        connection_created.disconnect(_on_connection_created)
        _apply_pragmas(connection, _RESTORE_PRAGMAS)
        with connection.cursor() as cursor:
            # TRUNCATE checkpoints the WAL and resets the file to a
            # single frame. Without this, the deferred-checkpoint
            # mode above leaves the WAL holding the import's worth
            # of frames until a reader transaction crosses them.
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            # Refresh planner statistics. SQLite's planner relies on
            # sqlite_stat1 etc., which are stale until ANALYZE
            # (or PRAGMA optimize) runs. Without this, the next few
            # browser queries plan against pre-import stats.
            cursor.execute("PRAGMA optimize")
