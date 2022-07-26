"""Vacuum the database."""
from django.db import connection
from humanize import naturalsize

from codex.librarian.status import librarian_status_done, librarian_status_update
from codex.settings.logging import get_logger
from codex.settings.settings import BACKUP_DB_PATH, DB_PATH


VACCUM_STATUS_KEYS = {"type": "Vacuum Database"}
BACKUP_STATUS_KEYS = {"type": "Backup Database"}
LOG = get_logger(__name__)


def vacuum_db():
    """Vacuum the database and report on savings."""
    librarian_status_update(VACCUM_STATUS_KEYS, 0, None)
    old_size = DB_PATH.stat().st_size
    with connection.cursor() as cursor:
        cursor.execute("VACUUM")
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    new_size = DB_PATH.stat().st_size
    saved = naturalsize(old_size - new_size)

    librarian_status_done([VACCUM_STATUS_KEYS])
    LOG.verbose(f"Vacuumed database. Saved {saved}.")


def backup_db():
    """Backup the database."""
    librarian_status_update(BACKUP_STATUS_KEYS, 0, None)
    BACKUP_DB_PATH.unlink(missing_ok=True)
    with connection.cursor() as cursor:
        cursor.execute(f"VACUUM INTO '{BACKUP_DB_PATH}'")
    librarian_status_done([BACKUP_STATUS_KEYS])
    LOG.verbose("Backed up database.")
