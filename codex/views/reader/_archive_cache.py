"""
Process-wide caches for the reader page endpoint.

Two related caches live in this module — both keyed on a comic pk and
both wired into ``ReaderPageView`` — sized independently because they
guard different costs:

1. ``ArchiveCache`` (``archive_cache``) — open ``Comicbox`` instances
   keyed on file path. Without it, every page hit re-opens the
   archive; a 200-page sequential read = 200 opens, and the web
   reader's prev / curr / next prefetch + the opt-in ``cacheBook``
   whole-book prefetch compound the redundancy. Per-archive
   ``threading.Lock`` serializes extraction because ZipFile / RarFile
   / PDF backends are not documented as thread-safe under concurrent
   ``read`` calls; the cache structure itself is guarded by a separate
   short-held lock so unrelated archives proceed in parallel.

2. ``PageAclCache`` (``page_acl_cache``) — ``(auth_key, comic_pk) →
   (path, file_type)``. Skips the per-page ACL-filter SQL within a
   short TTL window during a single read-through (sub-plan 03 #2 /
   Tier 4 #15).

Codex runs Granian in single-worker embed mode (see ``codex/run.py``)
so a single in-process LRU is shared by every request thread. Both
caches' defaults suit the constrained-NAS deployment shape (1-2 GB
RAM, ARM SBC etc.) — see ``tasks/reader-views-perf/stage3.md`` for
the telemetry-driven sizing rationale.

Configuration knobs (env vars):

* ``CODEX_READER_ARCHIVE_CACHE_SIZE`` — max open archives (default 4).
* ``CODEX_READER_ARCHIVE_CACHE_TTL`` — idle expiry in seconds (default 30).
* ``CODEX_READER_ARCHIVE_CACHE_DISABLE`` — bypass entirely (default off).
* ``CODEX_READER_PAGE_ACL_CACHE_SIZE`` — max ACL entries (default 64).
* ``CODEX_READER_PAGE_ACL_CACHE_TTL`` — TTL in seconds (default 60).
* ``CODEX_READER_PAGE_ACL_CACHE_DISABLE`` — bypass entirely (default off).
"""

from __future__ import annotations

import atexit
import os
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from typing import TYPE_CHECKING

from comicbox.box import Comicbox
from loguru import logger

from codex.settings import COMICBOX_CONFIG, FALSY

if TYPE_CHECKING:
    from collections.abc import Generator


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() not in FALSY


_DEFAULT_SIZE = 4
_DEFAULT_TTL = 30.0


class _ArchiveEntry:
    """One cached Comicbox + its per-path lock + last-access timestamp."""

    __slots__ = ("comicbox", "last_access", "lock", "path")

    def __init__(self, path: str, comicbox: Comicbox, last_access: float) -> None:
        self.path = path
        self.comicbox = comicbox
        self.lock = threading.Lock()
        self.last_access = last_access

    def close(self) -> None:
        """Close the cached archive; tolerate already-closed state."""
        try:
            self.comicbox.close()
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(f"closing cached archive {self.path}: {exc}")


class ArchiveCache:
    """Process-wide LRU of open Comicbox archives."""

    def __init__(
        self,
        max_entries: int = _DEFAULT_SIZE,
        idle_ttl: float = _DEFAULT_TTL,
        *,
        enabled: bool = True,
    ) -> None:
        self.max_entries = max_entries
        self.idle_ttl = idle_ttl
        self.enabled = enabled
        # ``_struct_lock`` guards LRU mutation only — held briefly for
        # dict ops. Per-archive locks (on each ``_ArchiveEntry``) guard
        # actual page extraction so unrelated archives proceed in
        # parallel.
        self._struct_lock = threading.Lock()
        self._archives: OrderedDict[str, _ArchiveEntry] = OrderedDict()

    # ── Internals ──────────────────────────────────────────────────────

    def _evict_expired(self, now: float) -> None:
        """Drop entries idle longer than ``idle_ttl``. Caller holds ``_struct_lock``."""
        expired_paths = [
            path
            for path, entry in self._archives.items()
            if now - entry.last_access > self.idle_ttl
        ]
        for path in expired_paths:
            entry = self._archives.pop(path)
            entry.close()

    def _evict_lru(self) -> None:
        """Drop the least-recently-used entry. Caller holds ``_struct_lock``."""
        _, entry = self._archives.popitem(last=False)
        entry.close()

    def _open_or_get(self, path: str) -> _ArchiveEntry:
        """Return the cached entry for ``path``, opening it if missing."""
        now = time.monotonic()
        with self._struct_lock:
            self._evict_expired(now)
            entry = self._archives.get(path)
            if entry is not None:
                # Hit — bump LRU position and refresh last_access.
                self._archives.move_to_end(path)
                entry.last_access = now
                return entry
            # Miss — open under the struct lock to prevent two threads
            # opening the same archive concurrently. The Comicbox
            # constructor returns immediately; the underlying archive
            # opens lazily on first access. Either way the open cost is
            # paid once per cache lifetime, not once per request.
            comicbox = Comicbox(path, config=COMICBOX_CONFIG, logger=logger)
            entry = _ArchiveEntry(path, comicbox, now)
            self._archives[path] = entry
            while len(self._archives) > self.max_entries:
                self._evict_lru()
            return entry

    # ── Public API ─────────────────────────────────────────────────────

    @contextmanager
    def open(self, path: str) -> Generator[Comicbox]:
        """
        Yield a ``Comicbox`` ready for ``get_page_by_index`` calls.

        Holds the per-archive lock for the duration of the yielded
        block so concurrent extraction on the same archive serializes
        correctly. Different archives proceed in parallel.

        When the cache is disabled, opens (and closes) a fresh
        ``Comicbox`` per call — same behaviour as the pre-cache code.
        """
        if not self.enabled:
            with Comicbox(path, config=COMICBOX_CONFIG, logger=logger) as cb:
                yield cb
            return
        entry = self._open_or_get(path)
        with entry.lock:
            yield entry.comicbox

    def shutdown(self) -> None:
        """Close every cached archive. Wired to ``atexit`` at module load."""
        with self._struct_lock:
            for entry in self._archives.values():
                entry.close()
            self._archives.clear()


# ── Module-level singleton ────────────────────────────────────────────

archive_cache = ArchiveCache(
    max_entries=_env_int("CODEX_READER_ARCHIVE_CACHE_SIZE", _DEFAULT_SIZE),
    idle_ttl=float(_env_int("CODEX_READER_ARCHIVE_CACHE_TTL", int(_DEFAULT_TTL))),
    enabled=not _env_bool("CODEX_READER_ARCHIVE_CACHE_DISABLE", default=False),
)

atexit.register(archive_cache.shutdown)


# ──────────────────────────────────────────────────────────────────────
# Page-endpoint ACL decision cache (sub-plan 03 #2 / Tier 4 #15)
# ──────────────────────────────────────────────────────────────────────
#
# A second, smaller cache keyed on ``(auth_key, comic_pk)`` →
# ``(path, file_type)``. Sequential reads of an N-page comic hit the
# page endpoint N times for the same ``(user, comic)``; without this
# cache each one re-runs the ACL filter SQL just to fetch path +
# file_type. Same trade-off as the archive cache (60 s TTL bounds
# staleness on ACL revocation / comic deletion) but a separate
# concern with separate sizing.

_PAGE_ACL_DEFAULT_SIZE = 64
_PAGE_ACL_DEFAULT_TTL = 60.0


class PageAclCache:
    """Process-wide LRU of (auth_key, comic_pk) → (path, file_type)."""

    def __init__(
        self,
        max_entries: int = _PAGE_ACL_DEFAULT_SIZE,
        ttl: float = _PAGE_ACL_DEFAULT_TTL,
        *,
        enabled: bool = True,
    ) -> None:
        self.max_entries = max_entries
        self.ttl = ttl
        self.enabled = enabled
        self._lock = threading.Lock()
        # Values stored as ``(path, file_type, expires_at)`` tuples.
        self._cache: OrderedDict[tuple, tuple[str, str | None, float]] = OrderedDict()

    def get(self, key: tuple, now: float) -> tuple[str, str | None] | None:
        """Return cached ``(path, file_type)`` or ``None`` if missing/expired."""
        if not self.enabled:
            return None
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            path, file_type, expires_at = entry
            if now >= expires_at:
                self._cache.pop(key, None)
                return None
            self._cache.move_to_end(key)
            return path, file_type

    def put(self, key: tuple, path: str, file_type: str | None, now: float) -> None:
        """Insert / refresh ``(path, file_type)`` for ``key``."""
        if not self.enabled:
            return
        expires_at = now + self.ttl
        with self._lock:
            self._cache[key] = (path, file_type, expires_at)
            self._cache.move_to_end(key)
            while len(self._cache) > self.max_entries:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        """Drop every entry. Useful for tests."""
        with self._lock:
            self._cache.clear()


page_acl_cache = PageAclCache(
    max_entries=_env_int("CODEX_READER_PAGE_ACL_CACHE_SIZE", _PAGE_ACL_DEFAULT_SIZE),
    ttl=float(_env_int("CODEX_READER_PAGE_ACL_CACHE_TTL", int(_PAGE_ACL_DEFAULT_TTL))),
    enabled=not _env_bool("CODEX_READER_PAGE_ACL_CACHE_DISABLE", default=False),
)
