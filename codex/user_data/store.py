"""
Sidecar SQLite store.

A thread-local, lazily-opened SQLite connection to ``user_data.sqlite``
in ``CODEX_CONFIG_DIR``. Each process opens its own connection on first
write. SQLite WAL mode handles cross-process concurrency; per-row
writes are sub-millisecond on local disk, so signal handlers write
in-line rather than enqueuing onto a drain thread.

The store raises on I/O errors. Callers (signal handlers) wrap calls
in ``try/except`` and log; sidecar failures never propagate into the
main request or librarian path. See :mod:`codex.user_data.signals`.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

SCHEMA_VERSION: Final[int] = 1
_SCHEMA_PATH: Final[Path] = Path(__file__).with_name("schema.sql")

# Matches main DB pragmas. ``foreign_keys=OFF`` is deliberate: the
# sidecar holds *denormalized* mirrors keyed on stable identifiers, so
# enforcing FKs against a non-existent main DB during restore would be
# wrong.
_PRAGMAS: Final[tuple[str, ...]] = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=OFF",
    "PRAGMA busy_timeout=5000",
)

_IS_EMPTY_TABLES_SQL: Final[str] = """\
SELECT name FROM sqlite_master
WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'schema_version'
"""


class SidecarStore:
    """Per-process sidecar SQLite store with thread-local connections."""

    def __init__(self, path: Path) -> None:
        """Bind the store to a sidecar file path. The file is not opened yet."""
        self._path = path
        # ``:memory:`` builds a throwaway snapshot we serialize to a
        # compressed dump (see ``dump.snapshot_sidecar``) — no file is touched.
        self._is_memory = str(path) == ":memory:"
        self._local = threading.local()
        # ``_schema_lock`` guards first-time DDL across threads in a
        # single process. SQLite handles cross-process concurrency via
        # WAL + busy_timeout.
        self._schema_lock = threading.Lock()
        self._schema_applied = False

    @classmethod
    def in_memory(cls) -> SidecarStore:
        """Build an ephemeral in-memory store (used to stage a dump snapshot)."""
        return cls(Path(":memory:"))

    @property
    def path(self) -> Path:
        """Sidecar file path."""
        return self._path

    def _open_connection(self) -> sqlite3.Connection:
        """Open a new connection for the current thread."""
        if self._is_memory:
            # A fresh anonymous in-memory DB; thread-local caching keeps the
            # single dump thread on this same connection so ``iterdump`` sees
            # the rows it just wrote.
            database = ":memory:"
        else:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            database = self._path
        # ``isolation_level=None`` puts sqlite3 into autocommit mode so
        # we manage transactions explicitly via ``with conn:`` blocks.
        conn = sqlite3.connect(
            database,
            isolation_level=None,
            timeout=5.0,
            check_same_thread=True,
        )
        conn.row_factory = sqlite3.Row
        for pragma in _PRAGMAS:
            conn.execute(pragma)
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        """Apply ``schema.sql`` and stamp the version row once per process."""
        if self._schema_applied:
            return
        with self._schema_lock:
            if self._schema_applied:
                return
            ddl = _SCHEMA_PATH.read_text(encoding="utf-8")
            with conn:
                conn.executescript(ddl)
                conn.execute(
                    "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
            self._schema_applied = True

    def connection(self) -> sqlite3.Connection:
        """Return the current thread's connection, opening it lazily."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._open_connection()
            self._local.conn = conn
        self._ensure_schema(conn)
        return conn

    def close(self) -> None:
        """Close the current thread's connection if open."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def upsert(
        self,
        table: str,
        key_columns: Iterable[str],
        data: Mapping[str, Any],
    ) -> None:
        """
        Insert or replace a row.

        ``key_columns`` names the primary-key columns (used to build the
        ``ON CONFLICT`` target). ``data`` includes both key and non-key
        columns. All columns in ``data`` are written; missing columns keep
        their schema defaults on insert, or their existing values on
        update (via ``ON CONFLICT ... DO UPDATE SET``).
        """
        columns = tuple(data.keys())
        if not columns:
            msg = f"upsert into {table} with no columns"
            raise ValueError(msg)
        key_tuple = tuple(key_columns)
        non_key = tuple(c for c in columns if c not in key_tuple)
        placeholders = ", ".join("?" for _ in columns)
        col_list = ", ".join(columns)
        if non_key:
            set_clause = ", ".join(f"{c}=excluded.{c}" for c in non_key)
            conflict_clause = (
                f" ON CONFLICT ({', '.join(key_tuple)}) DO UPDATE SET {set_clause}"
            )
        else:
            conflict_clause = f" ON CONFLICT ({', '.join(key_tuple)}) DO NOTHING"
        # Table and column names come from the sidecar's own schema, not
        # user input — interpolation is safe. Values go through positional
        # binding below.
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}){conflict_clause}"  # noqa: S608
        )
        conn = self.connection()
        with conn:
            conn.execute(sql, tuple(data[c] for c in columns))

    def delete(self, table: str, where: Mapping[str, Any]) -> None:
        """Delete rows from ``table`` matching every column in ``where``."""
        if not where:
            msg = f"delete with empty where clause: {table!r}"
            raise ValueError(msg)
        clause = " AND ".join(f"{c}=?" for c in where)
        # Table/column names are sidecar-schema-owned; values are bound.
        sql = f"DELETE FROM {table} WHERE {clause}"  # noqa: S608
        conn = self.connection()
        with conn:
            conn.execute(sql, tuple(where.values()))

    def fetchall(
        self,
        table: str,
        columns: Iterable[str] = ("*",),
    ) -> list[sqlite3.Row]:
        """Return every row of ``table``. Used by the restore path."""
        cols = ", ".join(columns)
        conn = self.connection()
        # Table/column names come from sidecar schema, not user input.
        return conn.execute(f"SELECT {cols} FROM {table}").fetchall()  # noqa: S608

    def is_empty(self) -> bool:
        """Return True when every tracked table is empty — gates backfill."""
        conn = self.connection()
        # Skip schema_version — it's stamped on schema creation.
        rows = conn.execute(_IS_EMPTY_TABLES_SQL).fetchall()
        return all(
            conn.execute(
                f"SELECT 1 FROM {row['name']} LIMIT 1"  # noqa: S608
            ).fetchone()
            is None
            for row in rows
        )


_store_lock: Final[threading.Lock] = threading.Lock()
_store: SidecarStore | None = None


def get_store() -> SidecarStore:
    """
    Return the process-wide sidecar store.

    Uses ``CONFIG_PATH / "user_data.sqlite"`` from Django settings. Importing
    settings happens lazily so this module is safe to import before
    ``django.setup()``.
    """
    global _store  # noqa: PLW0603
    if _store is not None:
        return _store
    with _store_lock:
        # Double-checked: another thread may have populated between the
        # first read and the lock acquisition. Pyright can't see this and
        # would call the inner return unreachable.
        if _store is not None:
            return _store  # pyright: ignore[reportUnreachable]
        from codex.settings import CONFIG_PATH

        _store = SidecarStore(CONFIG_PATH / "user_data.sqlite")
        logger.debug(f"Sidecar store bound to {_store.path}")
        return _store


def reset_store_for_tests(path: Path | None = None) -> SidecarStore | None:
    """Reset the singleton, optionally rebinding to a test path."""
    global _store  # noqa: PLW0603
    with _store_lock:
        if _store is not None:
            _store.close()
        _store = SidecarStore(path) if path is not None else None
        return _store
