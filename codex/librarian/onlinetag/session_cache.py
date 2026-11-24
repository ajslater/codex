"""
Cache-backed persistent state for the online tagging daemon.

Two things live in the dedicated ``tagging`` cache, namespaced under
``onlinetag:``:

- **pending prompts** — a dict keyed by deferred-prompt ``fingerprint``.
  Each entry is fully self-contained so a later, independent task can apply
  the admin's choice *without* the original tagging run's in-memory session:
  it carries the ``comics`` the question speaks for (each with the other
  sources that tagged it anyway, ``tagged_by``, and the issue ids they
  wrote, ``tagged_ids``, to which answering another prompt on the comic
  adds its source), the ``source``, the serialized ``candidates``, the
  match ``mode``, the write params (``formats``, ``delete_original``), and
  the run's ``source_order`` and ``merge_all_sources``, which keep a
  higher-priority source winning the merge when the answer is applied
  (prompts cached before those three existed lack them). Prompts persist
  with no TTL and deliberately survive daemon restarts — they linger until
  answered, skipped, or pruned (when their comic disappears). The
  deferred-prompt fingerprint is deterministic across processes, so a
  fresh session can replay the choice.

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
the nightly janitor sweep on the scribe thread; the admin views only read
prompts and enqueue tasks. A resolve runs only between scans, never inside
one, so its changes and a scan's persists take turns. The janitor's sweep
reads, prunes and writes back, so it and every writer here hold
:data:`TAGGING_STATE_LOCK`. Not to be confused with
:mod:`codex.librarian.onlinetag.session_state`, which holds the in-process
``SessionState`` for a running job.
"""

from __future__ import annotations

from functools import wraps
from threading import RLock
from typing import TYPE_CHECKING, Any

from codex.cache import tagging_cache as cache

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

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
#: Serializes every write to the online tagging state: the pending prompts
#: and active scan id here, and session_snapshot's snapshot, resolution
#: record and resume descriptor. The online tag thread and the nightly
#: janitor on the scribe thread both read, change and write them back, and
#: the file cache has no compare-and-set, so without it one thread's
#: write-back drops what the other wrote in between. The janitor holds it
#: for its whole sweep. Readers need none, as the file cache replaces an
#: entry whole. Reentrant, as the locked writers call one another.
TAGGING_STATE_LOCK = RLock()


def under_state_lock[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Run ``func`` holding :data:`TAGGING_STATE_LOCK`."""

    @wraps(func)
    def locked(*args: P.args, **kwargs: P.kwargs) -> R:
        with TAGGING_STATE_LOCK:
            return func(*args, **kwargs)

    return locked


def get_active_scan_id() -> str:
    """Return the id of the in-flight Pass-1 scan, or the empty string."""
    return cache.get(_SCAN_KEY, "") or ""


@under_state_lock
def set_active_scan_id(scan_id: str) -> None:
    """Persist the active scan id, or clear it when ``scan_id`` is empty."""
    if scan_id:
        cache.set(_SCAN_KEY, scan_id, timeout=_NO_TIMEOUT)
    else:
        cache.delete(_SCAN_KEY)


def get_pending_prompts() -> dict[str, Any]:
    """Return the pending-prompt map (fingerprint -> prompt dict)."""
    return cache.get(_PROMPTS_KEY, {}) or {}


@under_state_lock
def set_pending_prompts(prompts: dict[str, Any]) -> None:
    """Replace the pending-prompt map, or clear it when empty."""
    if prompts:
        cache.set(_PROMPTS_KEY, prompts, timeout=_NO_TIMEOUT)
    else:
        cache.delete(_PROMPTS_KEY)


def prompt_comics(prompt: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """
    Return every comic one prompt answers for, representative first.

    Comicbox fingerprints a deferred prompt at *series* level on purpose:
    every issue of a series collapses to one key so a single pick answers the
    whole run (see ``_prompt_fingerprint`` in comicbox's ``online_session``).
    One prompt therefore routinely stands for many comics, and the first one
    — the comic whose candidates were scored and are rendered in the review
    dialog — is the representative.

    Prompts cached before the list existed carry only the representative's
    ``pk`` / ``path``, which reads as a one-comic list.
    """
    comics = prompt.get("comics")
    if comics:
        return tuple(comic for comic in comics if comic.get("pk") is not None)
    pk = prompt.get("pk")
    if pk is None:
        return ()
    return ({"pk": pk, "path": prompt.get("path") or ""},)


def _note_comic(comic: dict[str, Any], ids: Mapping[str, int]) -> bool:
    """Add ``ids`` to one comic's tagged ids and sources; return whether new."""
    known = comic.get("tagged_ids") or {}
    if ids.items() <= known.items():
        return False
    comic["tagged_ids"] = {**known, **ids}
    tagged_by = [str(name) for name in comic.get("tagged_by") or ()]
    comic["tagged_by"] = [*tagged_by, *(name for name in ids if name not in tagged_by)]
    return True


def note_tagged_ids(
    prompt: dict[str, Any], written: Mapping[int, Mapping[str, int]]
) -> bool:
    """
    Note on a prompt's comics the issue ids their queued writes carry.

    ``written`` maps a comic's pk to the issue id each source's write for it
    was queued with. Answering one source's prompt queues a write that the
    database only has once it is re-imported, so another source's prompt
    on the same comic, answered first, would apply alone. Noted here, its
    apply finds the id, as it does the ids the scan saw written, and the
    review dialog says that source already tagged the comic. The prompt's
    own source is never noted on it. Returns whether anything changed.
    """
    source = prompt.get("source")
    comics = [dict(comic) for comic in prompt_comics(prompt)]
    noted = [
        _note_comic(
            comic,
            {
                name: issue_id
                for name, issue_id in written.get(comic["pk"], {}).items()
                if name != source
            },
        )
        for comic in comics
    ]
    if not any(noted):
        return False
    prompt["comics"] = comics
    return True


@under_state_lock
def note_written_ids(written: Mapping[int, Mapping[str, int]]) -> bool:
    """
    Note queued writes' issue ids on every pending prompt and persist.

    Returns whether any prompt changed.
    """
    if not written:
        return False
    prompts = get_pending_prompts()
    changed = [note_tagged_ids(prompt, written) for prompt in prompts.values()]
    if any(changed):
        set_pending_prompts(prompts)
    return any(changed)


def _merge_prompt(
    existing: Mapping[str, Any], incoming: dict[str, Any]
) -> dict[str, Any]:
    """
    Fold an existing prompt's comics into the incoming one, newest winning.

    Every field but the comic list comes from the incoming prompt, so its
    representative and the candidates rendered for it stay describing the
    same comic. The lists union because a fingerprint arriving twice means
    *more* comics are waiting on that one answer, not that the earlier ones
    stopped waiting.
    """
    merged = dict(incoming)
    new_comics = prompt_comics(incoming)
    by_pk = {comic["pk"]: comic for comic in prompt_comics(existing)}
    for comic in new_comics:
        by_pk[comic["pk"]] = comic
    comics = list(by_pk.values())
    if new_comics:
        # Representative first, so it keeps owning the rendered candidates.
        representative_pk = new_comics[0]["pk"]
        comics.sort(key=lambda comic: comic["pk"] != representative_pk)
    merged["comics"] = comics
    return merged


@under_state_lock
def add_pending_prompts(new_prompts: dict[str, Any]) -> dict[str, Any]:
    """Merge ``new_prompts`` into the map (keyed by fingerprint) and persist."""
    if not new_prompts:
        return get_pending_prompts()
    prompts = get_pending_prompts()
    for fingerprint, prompt in new_prompts.items():
        existing = prompts.get(fingerprint)
        prompts[fingerprint] = _merge_prompt(existing, prompt) if existing else prompt
    set_pending_prompts(prompts)
    return prompts


@under_state_lock
def remove_pending_prompt(fingerprint: str) -> dict[str, Any]:
    """Drop one prompt by fingerprint and persist; return what remains."""
    prompts = get_pending_prompts()
    if prompts.pop(fingerprint, None) is not None:
        set_pending_prompts(prompts)
    return prompts


@under_state_lock
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


@under_state_lock
def clear_all() -> None:
    """Drop the active scan id and every pending prompt."""
    cache.delete_many((_SCAN_KEY, _PROMPTS_KEY))
