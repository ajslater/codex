"""Low level database utilities."""

import sqlite3
import subprocess
from threading import Event, Lock

from django.core.management import call_command
from django.db import DEFAULT_DB_ALIAS, connection, connections
from django.db.migrations.executor import MigrationExecutor
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.janitor.integrity import integrity_check
from codex.librarian.scribe.janitor.integrity.foreign_keys import fix_foreign_keys
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.librarian.scribe.janitor.tasks import JanitorFTSIntegrityCheckTask
from codex.settings import (
    BACKUP_DB_PATH,
    CONFIG_PATH,
    DB_PATH,
    FIX_FOREIGN_KEYS,
    FTS_INTEGRITY_CHECK,
    INTEGRITY_CHECK,
)
from codex.startup.custom_cover_libraries import cleanup_custom_cover_libraries
from codex.version import VERSION

_REPAIR_FLAG_PATH = CONFIG_PATH / "rebuild_db"
_REBUILT_DB_PATH = DB_PATH.parent / (DB_PATH.name + ".rebuilt")
_REPAIR_ARGS = ("sqlite3", DB_PATH, ".recover")
# ``sqlite3 .recover`` can stream a lot of SQL on a real-sized
# library; give it room to finish without spuriously timing out.
_REPAIR_TIMEOUT_S = 300
# WAL/SHM/journal sibling suffixes SQLite may write next to a DB.
# Stale ones left from an unclean shutdown contaminate every subsequent
# open until removed; warning about them at startup is the cheapest
# possible save for the operator.
_DB_SIBLING_SUFFIXES = ("-wal", "-shm", "-journal")


def _has_unapplied_migrations() -> bool:
    """Check if any migrations are outstanding."""
    try:
        connection = connections[DEFAULT_DB_ALIAS]
        connection.prepare_database()
        executor = MigrationExecutor(connection)
        targets = [
            key for key in executor.loader.graph.leaf_nodes() if key[0] == "codex"
        ]
        plan = executor.migration_plan(targets)
    except Exception as exc:
        logger.warning(f"has_unapplied_migrations(): {exc}")
        return False
    else:
        if result := bool(plan):
            logger.info("Database has migrations to apply after checks")
        return result


def _get_backup_db_path(prefix):
    suffix = f".{prefix}{BACKUP_DB_PATH.suffix}"
    return BACKUP_DB_PATH.with_suffix(suffix)


def _backup_db_before_migration() -> None:
    """If there are migrations to do, backup the db."""
    backup_path = _get_backup_db_path(f"before-v{VERSION}")
    janitor = Janitor(logger, LIBRARIAN_QUEUE, Lock(), event=Event())
    janitor.backup_db(show_status=False, backup_path=backup_path)
    logger.info("Backed up database before repairs and migrations")


def _repair_db(log, *, will_migrate: bool) -> None:
    """
    Run cheap, sync repairs ahead of migrations.

    FK + integrity checks gate the migration: a corrupt source
    dataset can fail an ``AlterField`` or ``RunPython`` mid-way and
    leave the schema half-migrated. Both are cheap relative to
    migration cost, so the up-front spend is well-targeted.

    FTS work is intentionally *not* here — a migration like 0039
    drops + recreates ``codex_comicfts``, so any rebuild done now
    is wasted. ``_queue_post_migration_fts_tasks`` defers FTS
    integrity to a librarian job that runs after migrate completes.
    """
    if FIX_FOREIGN_KEYS or will_migrate:
        fix_foreign_keys(log)
    if INTEGRITY_CHECK or will_migrate:
        integrity_check(log, long=True)
    cleanup_custom_cover_libraries(log)


def _queue_post_migration_fts_tasks(log) -> None:
    """
    Queue async FTS work that codex doesn't need to wait for.

    ``JanitorFTSIntegrityCheckTask`` auto-queues a rebuild on
    failure (see ``JanitorIntegrity.fts_integrity_check``), so the
    corruption case is self-healing without blocking startup.
    Codex serves browse / reader / OPDS requests immediately;
    search results are degraded only if the FTS table is empty or
    stale, and the regular ``SearchIndexSyncTask`` repopulates it.
    """
    if not FTS_INTEGRITY_CHECK:
        return
    LIBRARIAN_QUEUE.put(JanitorFTSIntegrityCheckTask())
    log.info("Scheduled post-migration FTS integrity check.")


def _rebuild_db() -> bool:
    """
    Dump and rebuild the database via ``sqlite3 .recover``.

    Gated on the ``rebuild_db`` sentinel file so this drastic path
    is operator-opt-in. Reads the recovery script as a single SQL
    blob and feeds it to ``executescript`` — ``.recover`` emits
    multi-line ``CREATE TABLE`` / ``CREATE TRIGGER`` definitions
    that don't survive being chopped at line boundaries and pushed
    through ``cursor.execute`` one-line-at-a-time, which the prior
    implementation did.
    """
    if not _REPAIR_FLAG_PATH.exists():
        return False

    logger.warning("REBUILDING DATABASE!!")
    _REBUILT_DB_PATH.unlink(missing_ok=True)
    with subprocess.Popen(  # noqa: S603
        _REPAIR_ARGS, stdout=subprocess.PIPE
    ) as recover_proc:
        try:
            stdout, _stderr = recover_proc.communicate(timeout=_REPAIR_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            recover_proc.kill()
            recover_proc.wait()
            logger.exception("sqlite3 .recover timed out; aborting rebuild.")
            return False

    if recover_proc.returncode != 0:
        logger.error(
            f"sqlite3 .recover exited with status {recover_proc.returncode}; aborting rebuild."
        )
        return False

    sql = stdout.decode()
    # ``.recover`` emits ``PRAGMA writable_schema = off;`` at the
    # tail; ``reset`` is the form sqlite3 expects after a recovery
    # write so the schema cache rebuilds cleanly.
    sql = sql.replace(
        "PRAGMA writable_schema = off;",
        "PRAGMA writable_schema = reset;",
    )
    with sqlite3.connect(_REBUILT_DB_PATH) as new_db_conn:
        new_db_conn.executescript(sql)

    backup_path = _get_backup_db_path("before-rebuild")
    DB_PATH.rename(backup_path)
    logger.info(f"Backed up old db to {backup_path}")
    _REBUILT_DB_PATH.replace(DB_PATH)
    _REPAIR_FLAG_PATH.unlink(missing_ok=True)
    logger.success("Rebuilt database. You may start codex normally now.")
    return True


def _warn_on_stale_wal_siblings() -> None:
    """
    Surface stale WAL/SHM/journal siblings before the first connect.

    SQLite treats those siblings as part of the database — every
    open replays whatever's in them on top of the main file. If a
    previous codex run was killed before clean shutdown (or a
    backup got dropped in next to leftover siblings), the merged
    state is internally inconsistent and the very first SQL Django
    runs after ``Database.connect`` raises
    ``sqlite3.DatabaseError: database disk image is malformed``.
    The wording is misleading: the main file alone is fine.

    A single ``ls``-shaped probe at the top of ``ensure_db_schema``
    converts that experience from a stack trace with no signal to a
    one-line warning that names the recovery action. We don't
    auto-delete: stale-looking siblings can also be a legitimate
    in-flight WAL from a fast restart, and silently nuking them
    would lose the last unckpointed transaction.
    """
    siblings = [
        DB_PATH.with_name(DB_PATH.name + suffix) for suffix in _DB_SIBLING_SUFFIXES
    ]
    present = [s for s in siblings if s.exists()]
    if not present:
        return
    main_mtime = DB_PATH.stat().st_mtime if DB_PATH.exists() else 0.0
    suspicious = [s for s in present if s.stat().st_mtime > main_mtime]
    if not suspicious:
        return
    suspicious_names = ", ".join(s.name for s in suspicious)
    cleanup_cmd = f"rm {DB_PATH}-wal {DB_PATH}-shm {DB_PATH}-journal"
    msg = (
        f"Stale SQLite siblings found newer than {DB_PATH.name}: {suspicious_names}."
        " These are usually left by a previous startup that was killed before clean"
        " shutdown, or by dropping a backup file next to leftover sibling files. If"
        " the next step fails with 'database disk image is malformed', remove them"
        f" with `{cleanup_cmd}` and try again."
    )
    logger.warning(msg)


def _migrate_silk_db() -> None:
    """Apply silk migrations to the silky DB when it's configured."""
    if "silky" not in connections.databases:
        return
    call_command("migrate", "silk", database="silky", verbosity=0)


def ensure_db_schema() -> bool:
    """Ensure the db is good and up to date."""
    logger.info("Ensuring database is correct and up to date...")
    if _rebuild_db():
        return False

    try:
        _warn_on_stale_wal_siblings()
        table_names = connection.introspection.table_names()
    except Exception:
        msg = (
            "Could not open database. If the file is corrupt, create "
            f"the sentinel file {_REPAIR_FLAG_PATH} and restart Codex."
            "the startup path will run sqlite3 .recover and rebuild."
        )
        logger.exception(msg)
        raise
    if "django_migrations" in table_names:
        # Cache the unapplied-migrations result so the backup,
        # repair, and post-migration paths all see the same answer
        # without each running its own SELECT against
        # ``django_migrations``.
        will_migrate = _has_unapplied_migrations()
        if will_migrate:
            _backup_db_before_migration()
        _repair_db(logger, will_migrate=will_migrate)
    call_command("migrate")
    _migrate_silk_db()
    _queue_post_migration_fts_tasks(logger)
    logger.success("Database ready.")
    return True
