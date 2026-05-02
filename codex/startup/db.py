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
    """Dump and rebuild the database."""
    # Drastic
    if not _REPAIR_FLAG_PATH.exists():
        return False

    logger.warning("REBUILDING DATABASE!!")
    _REBUILT_DB_PATH.unlink(missing_ok=True)
    recover_proc = subprocess.Popen(_REPAIR_ARGS, stdout=subprocess.PIPE)  # noqa: S603
    with sqlite3.connect(_REBUILT_DB_PATH) as new_db_conn, new_db_conn as new_db_cur:
        if recover_proc.stdout:
            for line in recover_proc.stdout:
                row = line.decode().strip()
                replaced_row = (
                    "PRAGMA writable_schema = reset;"
                    if row == "PRAGMA writable_schema = off;"
                    else row
                )
                new_db_cur.execute(replaced_row)
    if recover_proc.stdout:
        recover_proc.stdout.close()
        recover_proc.wait(timeout=15)

    backup_path = _get_backup_db_path("before-rebuild")
    DB_PATH.rename(backup_path)
    logger.info("Backed up old db to %s", backup_path)
    _REBUILT_DB_PATH.replace(DB_PATH)
    _REPAIR_FLAG_PATH.unlink(missing_ok=True)
    logger.success("Rebuilt database. You may start codex normally now.")
    return True


def _migrate_silk_db() -> None:
    """Apply silk migrations to the silky DB when it's configured."""
    if "silky" not in connections.databases:
        return
    call_command("migrate", "silk", database="silky", verbosity=0)


def ensure_db_schema() -> bool:
    """Ensure the db is good and up to date."""
    logger.info("Ensuring database is correct and up to date...")
    table_names = connection.introspection.table_names()
    if "django_migrations" in table_names:
        # Cache the unapplied-migrations result so the backup,
        # repair, and post-migration paths all see the same answer
        # without each running its own SELECT against
        # ``django_migrations``.
        will_migrate = _has_unapplied_migrations()
        if will_migrate:
            _backup_db_before_migration()
        if _rebuild_db():
            return False
        _repair_db(logger, will_migrate=will_migrate)
    call_command("migrate")
    _migrate_silk_db()
    _queue_post_migration_fts_tasks(logger)
    logger.success("Database ready.")
    return True
