"""
Cache-backed persistent state for the online tagging daemon.

Two things live in the dedicated ``tagging`` cache, namespaced under
``onlinetag:``:

- **pending prompts** — a dict keyed by deferred-prompt ``fingerprint``.
  Each entry is fully self-contained so a later, independent task can apply
  the admin's choice *without* the original tagging run's in-memory session:
  it carries the comic ``pk`` and ``path``, the ``source``, the serialized
  ``candidates``, the match ``mode``, and the write params (``formats``,
  ``delete_original``). Prompts persist with no TTL and deliberately survive
  daemon restarts — they linger until answered, skipped, or pruned (when
  their comic disappears). The deferred-prompt fingerprint is deterministic
  across processes, so a fresh session can replay the choice.

- **active scan id** — set only while a Pass-1 lookup is running, so the
  admin UI can show live progress and abort it. Unlike prompts, this is
  cleared at daemon startup: an in-flight scan cannot survive a restart.

This state lives in ``caches["tagging"]`` (a ``ResilientFileBasedCache``
with its own directory), NOT the default cache. Key prefixes are no
protection: Django's file-based ``cache.clear()`` deletes every entry
regardless of key, and the default cache is cleared after every import
that changed anything, on Library/Group CRUD, and at startup — any of
which would have stranded prompts mid-answer.

All writes happen on the single ``OnlineTagThread`` (run/resolve/skip) plus
the nightly janitor prune; the admin views only read prompts and enqueue
tasks. Not to be confused with
:mod:`codex.librarian.onlinetag.session_state`, which holds the in-process
``SessionState`` for a running job.
"""

from __future__ import annotations

from typing import Any

from codex.cache import tagging_cache as cache

_SCAN_KEY = "onlinetag:active_scan_id"
_PROMPTS_KEY = "onlinetag:pending_prompts"
#: The fingerprint scheme a stored prompt was built under. A prompt is
#: replayed by handing its fingerprint back to comicbox, so a prompt
#: fingerprinted under an older scheme can never be matched again: it
#: would sit in the queue forever, and answering it would silently do
#: nothing. Comicbox 5 changed the scheme, hence version 2.
PROMPT_VERSION = 2
# No TTL: pending prompts linger until answered/skipped/pruned; the active
# scan id is cleared explicitly at scan end and at daemon startup.
_NO_TIMEOUT = None


def get_active_scan_id() -> str:
    """Return the id of the in-flight Pass-1 scan, or the empty string."""
    return cache.get(_SCAN_KEY, "") or ""


def set_active_scan_id(scan_id: str) -> None:
    """Persist the active scan id, or clear it when ``scan_id`` is empty."""
    if scan_id:
        cache.set(_SCAN_KEY, scan_id, timeout=_NO_TIMEOUT)
    else:
        cache.delete(_SCAN_KEY)


def get_pending_prompts() -> dict[str, Any]:
    """Return the pending-prompt map (fingerprint -> prompt dict)."""
    return cache.get(_PROMPTS_KEY, {}) or {}


def set_pending_prompts(prompts: dict[str, Any]) -> None:
    """Replace the pending-prompt map, or clear it when empty."""
    if prompts:
        cache.set(_PROMPTS_KEY, prompts, timeout=_NO_TIMEOUT)
    else:
        cache.delete(_PROMPTS_KEY)


def add_pending_prompts(new_prompts: dict[str, Any]) -> dict[str, Any]:
    """Merge ``new_prompts`` into the map (keyed by fingerprint) and persist."""
    if not new_prompts:
        return get_pending_prompts()
    prompts = get_pending_prompts()
    prompts.update(new_prompts)
    set_pending_prompts(prompts)
    return prompts


def remove_pending_prompt(fingerprint: str) -> dict[str, Any]:
    """Drop one prompt by fingerprint and persist; return what remains."""
    prompts = get_pending_prompts()
    if prompts.pop(fingerprint, None) is not None:
        set_pending_prompts(prompts)
    return prompts


def prune_stale_prompts() -> int:
    """
    Drop prompts fingerprinted under an older scheme; return how many.

    Cheap and idempotent, so it runs at daemon start and again nightly
    rather than as a migration: the tagging cache lives under the config
    directory, where a test run's migrations would reach a developer's
    live prompts.
    """
    prompts = get_pending_prompts()
    if not prompts:
        return 0
    kept = {
        fingerprint: prompt
        for fingerprint, prompt in prompts.items()
        if prompt.get("prompt_version") == PROMPT_VERSION
    }
    dropped = len(prompts) - len(kept)
    if dropped:
        set_pending_prompts(kept)
    return dropped


def clear_all() -> None:
    """Drop the active scan id and every pending prompt."""
    cache.delete_many((_SCAN_KEY, _PROMPTS_KEY))
