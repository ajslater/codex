"""
Cache-backed transient state for the online tagging daemon.

The active session ID and the pending-prompts payload used to live on
the :class:`ComicboxTaggingDefaults` singleton row. That conflated
persistent admin configuration (credentials, default formats) with
operational state that only matters while a tagging job is in flight,
so the two fields moved to the Django cache.

Codex's default cache backend is ``ResilientFileBasedCache``, which
persists across restarts — important because the onlinetagd daemon's
``run_start`` deliberately clears the cached session at boot to avoid
adopting a stale ID, and the admin views read these values to render
the live tagging dialog.

The keys live behind tiny accessors so any future migration to a
different store (Redis, etc.) is a single-module change. Not to be
confused with :mod:`codex.librarian.onlinetag.session_state`, which
holds the in-process ``SessionState`` dataclass for a running job.
"""

from __future__ import annotations

from typing import Any

from django.core.cache import cache

# Cache keys are intentionally namespaced under ``onlinetag:`` so a
# ``cache.clear()`` from a CRUD viewset doesn't strand them (clear()
# wipes the whole default cache). If you need granular invalidation,
# call ``clear_active_session`` directly.
_SESSION_KEY = "onlinetag:active_session_id"
_PROMPTS_KEY = "onlinetag:active_prompts"
# No TTL: tagging sessions can run for hours. The daemon explicitly
# clears at the end of a session, on cancel, and at process start.
_NO_TIMEOUT = None


def get_active_session_id() -> str:
    """Return the current session ID or the empty string when none is set."""
    return cache.get(_SESSION_KEY, "") or ""


def set_active_session_id(session_id: str) -> None:
    """Persist the active session ID, or clear it when ``session_id`` is empty."""
    if session_id:
        cache.set(_SESSION_KEY, session_id, timeout=_NO_TIMEOUT)
    else:
        cache.delete(_SESSION_KEY)


def get_active_prompts() -> list[Any]:
    """Return the pending-prompt payload as a list (empty when missing)."""
    return cache.get(_PROMPTS_KEY, []) or []


def set_active_prompts(prompts: list[Any]) -> None:
    """Persist the pending-prompt payload, or clear when empty."""
    if prompts:
        cache.set(_PROMPTS_KEY, prompts, timeout=_NO_TIMEOUT)
    else:
        cache.delete(_PROMPTS_KEY)


def clear_active_session() -> None:
    """Drop both the session ID and the pending prompts."""
    cache.delete_many((_SESSION_KEY, _PROMPTS_KEY))
