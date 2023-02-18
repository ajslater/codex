"""Vacuum the database."""
from django.db import connection
from humanize import naturalsize

from codex.librarian.janitor.status import JanitorStatusTypes
from codex.settings.settings import BACKUP_DB_DIR, BACKUP_DB_PATH, DB_PATH
from codex.worker_base import WorkerBaseMixin

_OLD_BACKUP_PATH = BACKUP_DB_PATH.with_suffix(BACKUP_DB_PATH.suffix + ".old")


class VacuumMixin(WorkerBaseMixin):
    """Vacuum methods for janitor."""

    def vacuum_db(self):
        """Vacuum the database and report on savings."""
        try:
            self.status_controller.start(JanitorStatusTypes.DB_VACUUM)
            old_size = DB_PATH.stat().st_size
            with connection.cursor() as cursor:
                cursor.execute("VACUUM")
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            new_size = DB_PATH.stat().st_size
            saved = naturalsize(old_size - new_size)
            self.log.info(f"Vacuumed database. Saved {saved}.")
        finally:
            self.status_controller.finish(JanitorStatusTypes.DB_VACUUM)

    def backup_db(self, backup_path=BACKUP_DB_PATH):
        """Backup the database."""
        try:
            self.status_controller.start(JanitorStatusTypes.DB_BACKUP)
            BACKUP_DB_DIR.mkdir(exist_ok=True, parents=True)
            if backup_path.is_file():
                backup_path.replace(_OLD_BACKUP_PATH)
            path = str(backup_path)
            with connection.cursor() as cursor:
                cursor.execute(f"VACUUM INTO {path!r}")
            _OLD_BACKUP_PATH.unlink(missing_ok=True)
            self.log.info(f"Backed up database to {path}")
        except Exception as exc:
            self.log.error("Backing up database.")
            self.log.exception(exc)
        finally:
            self.status_controller.finish(JanitorStatusTypes.DB_BACKUP)
