"""Vacuum the database."""

import re
import sqlite3

from django.db import connection
from humanize import naturalsize

from codex.librarian.memory import read_mem_limit
from codex.librarian.scribe.janitor.integrity import JanitorIntegrity
from codex.librarian.scribe.janitor.status import (
    JanitorDBBackupStatus,
    JanitorDBOptimizeStatus,
    JanitorDumpUserDataStatus,
)
from codex.settings import BACKUP_DB_DIR, BACKUP_DB_PATH, DB_PATH
from codex.xz import (
    XZ_SUFFIX,
    compress_path_to_xz,
    date_stamp,
    prune_dated,
    write_xz_bytes,
    xz_preset,
)

# Pre-dating single backup + its rotated sibling, removed once dated
# ``.bak.xz`` backups exist.
_OLD_BACKUP_PATH = BACKUP_DB_PATH.with_suffix(BACKUP_DB_PATH.suffix + ".old")
# Dated nightly DB backups: ``codex.sqlite3.<ISO-date>.bak.xz``. The date class
# excludes the ``before-v*`` upgrade backups, which are retained indefinitely.
_NIGHTLY_BACKUP_PATTERN = (
    rf"^{re.escape(DB_PATH.name)}\.\d{{4}}-\d{{2}}-\d{{2}}\.bak\.xz$"
)
# A DB up to this share of the memory budget is backed up via the fast,
# single-write ``serialize()`` path (its image is held in RAM); a larger DB
# falls back to ``VACUUM INTO`` a temp file + chunked compression so peak
# memory stays bounded on small / cgroup-capped hosts.
_SERIALIZE_MAX_FRACTION = 0.5


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

        The xz preset and the backup method are both chosen from the host's
        cgroup-aware memory budget. When the DB fits comfortably in RAM,
        ``Connection.serialize()`` captures a consistent image in milliseconds
        (so ``db_write_lock`` is held only for the snapshot, not the slow
        compression). A DB too large for that falls back to ``VACUUM INTO`` a
        temp file + chunked compression, bounding peak memory on small hosts.
        Either way the FTS5 index stays byte-for-byte intact (a SQL dump would
        drop it).

        ``backup_path=None`` writes a dated nightly backup and (with ``prune``)
        trims the dated set; an explicit ``backup_path`` (the before-upgrade
        backup) is compressed in place with no dating or pruning.
        """
        status = JanitorDBBackupStatus() if show_status else None
        try:
            if status:
                self.status_controller.start(status)
            backup_path = self._resolve_backup_path(backup_path)
            self._write_backup(backup_path)
            if prune:
                self._prune_dated_backups()
            self.log.info(f"Backed up database to {backup_path}")
        except Exception:
            self.log.exception("Backing up database.")
        finally:
            if status:
                self.status_controller.finish(status)

    @staticmethod
    def _resolve_backup_path(backup_path):
        """Dated nightly name when unset; else the caller's path + ``.xz``."""
        if backup_path is None:
            return BACKUP_DB_DIR / f"{DB_PATH.name}.{date_stamp()}.bak.xz"
        return backup_path.with_name(backup_path.name + XZ_SUFFIX)

    def _write_backup(self, backup_path) -> None:
        """Pick the serialize vs ``VACUUM INTO`` path from the memory budget."""
        budget = read_mem_limit("b")
        preset = xz_preset(budget)
        db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
        if db_size <= budget * _SERIALIZE_MAX_FRACTION:
            self._backup_db_serialize(backup_path, preset)
        else:
            self._backup_db_vacuum(backup_path, preset)

    @staticmethod
    def _prune_dated_backups() -> None:
        """Trim the dated nightly set and remove the pre-dating single backups."""
        prune_dated(BACKUP_DB_DIR, _NIGHTLY_BACKUP_PATTERN)
        _OLD_BACKUP_PATH.unlink(missing_ok=True)
        BACKUP_DB_PATH.unlink(missing_ok=True)

    def _backup_db_serialize(self, backup_path, preset) -> None:
        """Fast path: snapshot a consistent image under the lock, compress free."""
        with self.db_write_lock:
            connection.ensure_connection()
            data = connection.connection.serialize()
        write_xz_bytes(data, backup_path, preset=preset)
        del data

    def _backup_db_vacuum(self, backup_path, preset) -> None:
        """Bounded-memory path: VACUUM to a temp DB, then chunked compression."""
        BACKUP_DB_DIR.mkdir(parents=True, exist_ok=True)
        tmp_db = BACKUP_DB_DIR / f"{DB_PATH.name}.backup.tmp"
        tmp_db.unlink(missing_ok=True)
        try:
            # ``VACUUM INTO`` can't run inside a transaction. Use a dedicated
            # autocommit connection to the DB file so the backup is immune to
            # the caller's transaction state; the write lock keeps Python
            # writers out for a consistent image, matching ``vacuum_db``.
            with self.db_write_lock:
                raw = sqlite3.connect(DB_PATH, isolation_level=None)
                try:
                    raw.execute(f"VACUUM INTO {str(tmp_db)!r}")
                finally:
                    raw.close()
            compress_path_to_xz(tmp_db, backup_path, preset=preset)
        finally:
            tmp_db.unlink(missing_ok=True)

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
