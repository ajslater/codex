"""
Cache-backed collection of tag-write errors for admin feedback.

Writing tags edits the comic archive files on disk. When a write fails
(a read-only mount, a permission error, a corrupt archive, …) comicbox
returns the exception on its result object and :class:`TagWriter` would
otherwise only log it. These accessors persist those failures so the
admin Tagging tab can present them and clear them.

The store is the dedicated ``tagging`` Django cache (a
``ResilientFileBasedCache``), *not* the database — the failures are
operational feedback, not durable records. The file-based cache persists
across restarts, so an admin who sees the red badge after a restart still
finds the errors waiting. The default cache would not do: its broad
``cache.clear()`` calls (import finish, Library/Group CRUD, startup)
delete every entry regardless of key prefix. Use
:func:`clear_tag_write_errors` for granular clearing.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from codex.cache import tagging_cache as cache

_ERRORS_KEY = "tagwrite:errors"
# No TTL: errors persist until the admin clears them.
_NO_TIMEOUT = None
# Cap the list so a pathological run (e.g. an entire read-only library)
# can't grow the cached blob without bound. Newest errors win.
_MAX_ERRORS = 100


def add_tag_write_error(path: str, error: str) -> None:
    """Record a tag-write failure, newest first, deduped by path."""
    errors: list[dict[str, Any]] = cache.get(_ERRORS_KEY, []) or []
    # Drop any prior entry for the same path so a retry replaces it
    # instead of stacking duplicates.
    errors = [entry for entry in errors if entry.get("path") != path]
    errors.insert(
        0,
        {"path": path, "error": error, "time": timezone.now().isoformat()},
    )
    del errors[_MAX_ERRORS:]
    cache.set(_ERRORS_KEY, errors, timeout=_NO_TIMEOUT)


def get_tag_write_errors() -> list[dict[str, Any]]:
    """Return the collected tag-write errors (newest first, empty when none)."""
    return cache.get(_ERRORS_KEY, []) or []


def clear_tag_write_errors() -> None:
    """Drop all collected tag-write errors."""
    cache.delete(_ERRORS_KEY)
