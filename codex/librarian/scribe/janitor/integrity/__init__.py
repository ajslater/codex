"""Database integrity checks and remedies."""

# Uses app.get_model() because functions may also be called before the models are ready on startup.

from django.db import DEFAULT_DB_ALIAS, connections

from codex.librarian.scribe.janitor.integrity.foreign_keys import fix_foreign_keys
from codex.librarian.scribe.janitor.status import (
    JanitorDBFKIntegrityStatus,
    JanitorDBFTSIntegrityStatus,
    JanitorDBFTSRebuildStatus,
    JanitorDBIntegrityStatus,
)
from codex.librarian.scribe.janitor.tasks import JanitorFTSRebuildTask
from codex.librarian.worker import WorkerStatusAbortableBase


def _exec_sql(sql):
    """Run sql on an potentially unready database.."""
    connection = connections[DEFAULT_DB_ALIAS]
    connection.prepare_database()
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        cursor.execute(sql)
        return cursor.fetchall()


def _is_integrity_ok(results) -> bool:
    return (
        results and len(results) == 1 and len(results[0]) == 1 and results[0][0] == "ok"
    )


def integrity_check(log, *, long: bool) -> None:
    """Run sqlite3 integrity check."""
    pragma = "integrity_check" if long else "quick_check"
    sql = f"PRAGMA {pragma};"
    log.debug(f"Running database '{sql}'...")
    results = _exec_sql(sql)

    if _is_integrity_ok(results):
        length = "" if long else "quick "
        log.success(f"Database passed {length}integrity check.")
    else:
        log.warning(f"Database '{sql}' returned results:")
        log.warning(results)
        log.warning(
            "See the README for database rebuild instructions if the above warning looks severe."
        )


def fts_rebuild() -> None:
    """FTS Rebuild."""
    _exec_sql("INSERT INTO codex_comicfts (codex_comicfts) VALUES('rebuild');")


def fts_integrity_check(log) -> bool:
    """Run sqlite3 fts integrity check."""
    results = []
    sql = "INSERT INTO codex_comicfts (codex_comicfts) VALUES('integrity-check');"
    success = False
    results = []
    try:
        results = _exec_sql(sql)
        if results:
            # I'm not sure if this raises or puts the error in the results.
            raise ValueError(results)  # noqa: TRY301
        log.success("Full Text Search Index passed integrity check.")
        success = True
    except Exception:
        log.exception("Full Text Search Index failed integrity check")
        log.debug(results)
    return success


class JanitorIntegrity(WorkerStatusAbortableBase):
    """Integrity Check Mixin."""

    def foreign_key_check(self) -> None:
        """Foreign Key Check task."""
        status = JanitorDBFKIntegrityStatus()
        try:
            self.status_controller.start(status)
            with self.db_write_lock:
                fix_foreign_keys(self.log)
        finally:
            self.status_controller.finish(status)

    def integrity_check(self, *, long: bool) -> None:
        """Integrity check task."""
        subtitle = "" if long else "Quick"
        status = JanitorDBIntegrityStatus(subtitle=subtitle)
        try:
            self.status_controller.start(status)
            with self.db_write_lock:
                integrity_check(self.log, long=long)
        finally:
            self.status_controller.finish(status)

    def fts_rebuild(self) -> None:
        """FTS rebuild task."""
        status = JanitorDBFTSRebuildStatus()
        try:
            self.status_controller.start(status)
            with self.db_write_lock:
                fts_rebuild()
        finally:
            self.status_controller.finish(status)

    def fts_integrity_check(self) -> None:
        """FTS integrity check task."""
        status = JanitorDBFTSIntegrityStatus()
        try:
            self.status_controller.start(status)
            with self.db_write_lock:
                success = fts_integrity_check(self.log)
            if not success:
                self.librarian_queue.put(JanitorFTSRebuildTask())
        finally:
            self.status_controller.finish(status)
