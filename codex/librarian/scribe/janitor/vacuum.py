"""Vacuum the database."""

from django.db import connection
from humanize import naturalsize

from codex.librarian.scribe.janitor.integrity import JanitorIntegrity
from codex.librarian.scribe.janitor.status import (
    JanitorDBBackupStatus,
    JanitorDBOptimizeStatus,
)
from codex.settings import BACKUP_DB_DIR, BACKUP_DB_PATH, DB_PATH

_OLD_BACKUP_PATH = BACKUP_DB_PATH.with_suffix(BACKUP_DB_PATH.suffix + ".old")


class JanitorVacuum(JanitorIntegrity):
    """Vacuum methods for janitor."""

    def vacuum_db(self):
        """Vacuum the database and report on savings."""
        status = JanitorDBOptimizeStatus()
        try:
            self.status_controller.start(status)
            old_size = DB_PATH.stat().st_size
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA optimize")
                cursor.execute("VACUUM")
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            new_size = DB_PATH.stat().st_size
            saved = naturalsize(old_size - new_size)
            self.log.info(f"Vacuumed database. Saved {saved}.")
        finally:
            self.status_controller.finish(status)

    def backup_db(self, backup_path=BACKUP_DB_PATH, *, show_status: bool):
        """Backup the database."""
        status = JanitorDBBackupStatus() if show_status else None
        try:
            if status:
                self.status_controller.start(status)
            BACKUP_DB_DIR.mkdir(exist_ok=True, parents=True)
            if backup_path.is_file():
                backup_path.replace(_OLD_BACKUP_PATH)
            path = str(backup_path)
            with connection.cursor() as cursor:
                cursor.execute(f"VACUUM INTO {path!r}")
            _OLD_BACKUP_PATH.unlink(missing_ok=True)
            self.log.info(f"Backed up database to {path}")
        except Exception:
            self.log.exception("Backing up database.")
        finally:
            if status:
                self.status_controller.finish(status)
