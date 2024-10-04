"""Low level database utilities."""

import sqlite3
import subprocess

from django.core.management import call_command
from django.db import DEFAULT_DB_ALIAS, connection, connections
from django.db.migrations.executor import MigrationExecutor

from codex.librarian.janitor.integrity import (
    cleanup_custom_cover_libraries,
    fix_foreign_keys,
    fts_integrity_check,
    fts_rebuild,
    integrity_check,
)
from codex.librarian.janitor.janitor import Janitor
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.logger.mp_queue import LOG_QUEUE
from codex.settings.settings import (
    BACKUP_DB_PATH,
    CONFIG_PATH,
    DB_PATH,
    FIX_FOREIGN_KEYS,
    FTS_INTEGRITY_CHECK,
    FTS_REBUILD,
    INTEGRITY_CHECK,
)
from codex.version import VERSION

_REPAIR_FLAG_PATH = CONFIG_PATH / "rebuild_db"
_REBUILT_DB_PATH = DB_PATH.parent / (DB_PATH.name + ".rebuilt")
_REPAIR_ARGS = ("sqlite3", DB_PATH, ".recover")

LOG = get_logger(__name__)


def _has_unapplied_migrations():
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
        LOG.warning(f"has_unapplied_migrations(): {exc}")
        return False
    else:
        return bool(plan)


def _get_backup_db_path(prefix):
    suffix = f".{prefix}{BACKUP_DB_PATH.suffix}"
    return BACKUP_DB_PATH.with_suffix(suffix)


def _backup_db_before_migration():
    """If there are migrations to do, backup the db."""
    backup_path = _get_backup_db_path(f"before-v{VERSION}")
    janitor = Janitor(LOG_QUEUE, LIBRARIAN_QUEUE)
    janitor.backup_db(backup_path, show_status=False)
    LOG.info("Backed up database before migrations")


def _repair_db():
    """Run integrity checks on startup."""
    if FIX_FOREIGN_KEYS:
        fix_foreign_keys()
    if INTEGRITY_CHECK:
        integrity_check()
    success = fts_integrity_check() if FTS_INTEGRITY_CHECK else True
    if FTS_REBUILD or not success:
        fts_rebuild()
    cleanup_custom_cover_libraries()


def _rebuild_db():
    """Dump and rebuild the database."""
    # Drastic
    if not _REPAIR_FLAG_PATH.exists():
        return False

    LOG.warning("REBUILDING DATABASE!!")
    _REBUILT_DB_PATH.unlink(missing_ok=True)
    recover_proc = subprocess.Popen(_REPAIR_ARGS, stdout=subprocess.PIPE)  # noqa: S603
    with sqlite3.connect(_REBUILT_DB_PATH) as new_db_conn:
        new_db_cur = new_db_conn.cursor()
        if recover_proc.stdout:
            for line in recover_proc.stdout:
                row = line.decode().strip()
                replaced_row = (
                    "PRAGMA writable_schema = reset;"
                    if row == "PRAGMA writable_schema = off;"
                    else row
                )
                new_db_cur.execute(replaced_row)
        new_db_cur.close()
    if recover_proc.stdout:
        recover_proc.stdout.close()
        recover_proc.wait(timeout=15)

    backup_path = _get_backup_db_path("before-rebuild")
    DB_PATH.rename(backup_path)
    LOG.info("Backed up old db to %s", backup_path)
    _REBUILT_DB_PATH.replace(DB_PATH)
    _REPAIR_FLAG_PATH.unlink(missing_ok=True)
    LOG.info("Rebuilt database.")
    LOG.info("You may start codex normally now.")
    for handler in LOG.handlers:
        handler.flush()
    return True


def ensure_db_schema():
    """Ensure the db is good and up to date."""
    LOG.info("Ensuring database is correct and up to date...")
    table_names = connection.introspection.table_names()
    if db_exists := "django_migrations" in table_names:
        if _rebuild_db():
            return False
        _repair_db()

    if not db_exists or _has_unapplied_migrations():
        if db_exists:
            _backup_db_before_migration()
        call_command("migrate")
    else:
        LOG.info("Database up to date.")
    LOG.info("Database ready.")
    return True
