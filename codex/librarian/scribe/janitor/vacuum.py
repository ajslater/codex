"""Vacuum the database."""

import re

from django.db import connection
from humanize import naturalsize

from codex.compression import XZ_SUFFIX, date_stamp, prune_dated, write_xz_bytes
from codex.librarian.scribe.janitor.integrity import JanitorIntegrity
from codex.librarian.scribe.janitor.status import (
    JanitorDBBackupStatus,
    JanitorDBOptimizeStatus,
    JanitorDumpUserDataStatus,
)
from codex.settings import BACKUP_DB_DIR, BACKUP_DB_PATH, DB_PATH

# Pre-dating single backup + its rotated sibling, removed once dated
# ``.bak.xz`` backups exist.
_OLD_BACKUP_PATH = BACKUP_DB_PATH.with_suffix(BACKUP_DB_PATH.suffix + ".old")
# Dated nightly DB backups: ``codex.sqlite3.<ISO-date>.bak.xz``. The date class
# excludes the ``before-v*`` upgrade backups, which are retained indefinitely.
_NIGHTLY_BACKUP_PATTERN = (
    rf"^{re.escape(DB_PATH.name)}\.\d{{4}}-\d{{2}}-\d{{2}}\.bak\.xz$"
)


class JanitorVacuum(JanitorIntegrity):
    """Vacuum methods for janitor."""

    def vacuum_db(self) -> None:
        """Vacuum the database and report on savings."""
        status = JanitorDBOptimizeStatus()
        try:
            self.status_controller.start(status)
            old_size = DB_PATH.stat().st_size
            # ``VACUUM`` takes an exclusive lock at the SQLite level.
            # Acquire ``db_write_lock`` so a concurrent importer (or
            # any other Python-level writer) waits cleanly instead of
            # surfacing "database is locked" mid-bulk_create.
            with self.db_write_lock, connection.cursor() as cursor:
                cursor.execute("PRAGMA optimize")
                cursor.execute("VACUUM")
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            new_size = DB_PATH.stat().st_size
            saved = naturalsize(old_size - new_size)
            self.log.info(f"Vacuumed database. Saved {saved}.")
        finally:
            self.status_controller.finish(status)

    def backup_db(
        self, backup_path=None, *, show_status: bool, prune: bool = False
    ) -> None:
        """
        Back up the database as a streamed, xz-compressed binary snapshot.

        ``Connection.serialize()`` captures a consistent in-memory image in
        milliseconds, so the ``db_write_lock`` is held only for the snapshot —
        not the (slow) compression, which runs lock-free. ``serialize`` keeps
        the FTS5 search index byte-for-byte intact, which a SQL dump would not.

        ``backup_path=None`` writes a dated nightly backup and (with ``prune``)
        trims the dated set; an explicit ``backup_path`` (the before-upgrade
        backup) is compressed in place with no dating or pruning.
        """
        status = JanitorDBBackupStatus() if show_status else None
        try:
            if status:
                self.status_controller.start(status)
            if backup_path is None:
                backup_path = BACKUP_DB_DIR / f"{DB_PATH.name}.{date_stamp()}.bak.xz"
            else:
                backup_path = backup_path.with_name(backup_path.name + XZ_SUFFIX)
            with self.db_write_lock:
                connection.ensure_connection()
                data = connection.connection.serialize()
            write_xz_bytes(data, backup_path)
            del data
            if prune:
                prune_dated(BACKUP_DB_DIR, _NIGHTLY_BACKUP_PATTERN)
                _OLD_BACKUP_PATH.unlink(missing_ok=True)
                BACKUP_DB_PATH.unlink(missing_ok=True)
            self.log.info(f"Backed up database to {backup_path}")
        except Exception:
            self.log.exception("Backing up database.")
        finally:
            if status:
                self.status_controller.finish(status)

    def dump_user_data_sidecar(self) -> None:
        """
        Snapshot every user-bound row into the user-data sidecar.

        Reads the main DB only; the sidecar lives in a separate SQLite
        file under ``CODEX_CONFIG_DIR``, so this doesn't compete for
        ``db_write_lock`` with importers / vacuums on the main DB.
        Failures are caught and logged — the nightly task should never
        block the rest of the janitor pipeline on a sidecar problem.
        """
        from codex.user_data.dump import snapshot_sidecar

        status = JanitorDumpUserDataStatus()
        try:
            self.status_controller.start(status)
            counts = snapshot_sidecar()
            total = sum(counts.values())
            self.log.info(f"Snapshotted user data sidecar: {total} rows")
        except Exception:
            self.log.exception("Sidecar dump failed.")
        finally:
            self.status_controller.finish(status)
