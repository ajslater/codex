"""Vacuum the database."""
from django.db import connection
from humanize import naturalsize

from codex.librarian.janitor.status import JanitorStatusTypes
from codex.librarian.status_control import StatusControl
from codex.settings.logging import get_logger
from codex.settings.settings import BACKUP_DB_PATH, DB_PATH


LOG = get_logger(__name__)


def vacuum_db():
    """Vacuum the database and report on savings."""
    try:
        StatusControl.start(JanitorStatusTypes.DB_VACUUM)
        old_size = DB_PATH.stat().st_size
        with connection.cursor() as cursor:
            cursor.execute("VACUUM")
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        new_size = DB_PATH.stat().st_size
        saved = naturalsize(old_size - new_size)
        LOG.verbose(f"Vacuumed database. Saved {saved}.")
    finally:
        StatusControl.finish(JanitorStatusTypes.DB_VACUUM)


def backup_db():
    """Backup the database."""
    try:
        StatusControl.start(JanitorStatusTypes.DB_BACKUP)
        BACKUP_DB_PATH.unlink(missing_ok=True)
        with connection.cursor() as cursor:
            cursor.execute(f"VACUUM INTO '{BACKUP_DB_PATH}'")
        LOG.verbose("Backed up database.")
    finally:
        StatusControl.finish(JanitorStatusTypes.DB_BACKUP)
