"""Vacuum the database."""
from django.db import connection
from humanize import naturalsize

from codex.settings.logging import get_logger
from codex.settings.settings import BACKUP_DB_PATH, DB_PATH


LOG = get_logger(__name__)


def vacuum_db():
    """Vacuum the database and report on savings."""
    old_size = DB_PATH.stat().st_size
    with connection.cursor() as cursor:
        cursor.execute("VACUUM")
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    new_size = DB_PATH.stat().st_size
    saved = naturalsize(old_size - new_size)

    LOG.verbose(f"Vacuumed database. Saved {saved}.")


def backup_db():
    """Backup the database."""
    BACKUP_DB_PATH.unlink(missing_ok=True)
    with connection.cursor() as cursor:
        cursor.execute(f"VACUUM INTO '{BACKUP_DB_PATH}'")
    LOG.verbose("Backed up database.")
