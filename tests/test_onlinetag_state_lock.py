"""
Every change to the online tagging state waits for the state lock.

The online tag thread and the nightly janitor on the scribe thread both
read, change and write back the tagging cache's shared state. The janitor
holds the lock for its whole sweep, so each of the online tag thread's
writes must wait for it, or the sweep's write-back drops it.
"""

from collections.abc import Callable
from threading import Thread
from typing import Final, override

from django.core.cache import caches
from django.test import SimpleTestCase

from codex.librarian.onlinetag.session_cache import (
    TAGGING_STATE_LOCK,
    add_pending_prompts,
    clear_all,
    get_active_scan_id,
    get_pending_prompts,
    note_written_ids,
    remove_pending_prompt,
    set_active_scan_id,
    set_pending_prompts,
)
from codex.librarian.onlinetag.session_snapshot import (
    clear_resolved_outcomes,
    clear_resume_state,
    clear_snapshot,
    deactivate_snapshot,
    get_resolved_outcomes,
    get_resume_state,
    get_snapshot,
    record_resolution,
    set_resolved_outcomes,
    set_resume_state,
    set_snapshot,
)
from codex.librarian.onlinetag.statuses import USER_MATCHED

# Ample for an unblocked write; a write waiting on the lock never ends.
_BLOCKED_WAIT_S: Final = 0.2
_PROMPT: Final = {"source": "comicvine", "comics": [{"pk": 1, "path": "/c1.cbz"}]}


def _noop() -> None:
    pass


def _seed_prompt() -> None:
    set_pending_prompts({"fp": dict(_PROMPT)})


def _seed_scan() -> None:
    set_active_scan_id("scan-1")


def _seed_resolution() -> None:
    record_resolution(1, USER_MATCHED, "metron")


def _seed_resume() -> None:
    set_resume_state({}, [1])


def _seed_snapshot() -> None:
    set_snapshot({"active": True, "comics": []})


def _snapshot_inactive() -> bool:
    snapshot = get_snapshot()
    return snapshot is not None and snapshot["active"] is False


#: (writer, seed, the write, whether it has landed)
_WRITERS: Final[
    tuple[tuple[str, Callable[[], None], Callable[[], object], Callable[[], bool]], ...]
] = (
    (
        "set_pending_prompts",
        _noop,
        lambda: set_pending_prompts({"fp": dict(_PROMPT)}),
        lambda: "fp" in get_pending_prompts(),
    ),
    (
        "add_pending_prompts",
        _noop,
        lambda: add_pending_prompts({"fp": dict(_PROMPT)}),
        lambda: "fp" in get_pending_prompts(),
    ),
    (
        "remove_pending_prompt",
        _seed_prompt,
        lambda: remove_pending_prompt("fp"),
        lambda: "fp" not in get_pending_prompts(),
    ),
    (
        "note_written_ids",
        _seed_prompt,
        lambda: note_written_ids({1: {"metron": 101}}),
        lambda: bool(get_pending_prompts()["fp"]["comics"][0].get("tagged_ids")),
    ),
    (
        "set_active_scan_id",
        _noop,
        lambda: set_active_scan_id("scan-1"),
        lambda: get_active_scan_id() == "scan-1",
    ),
    (
        "clear_all",
        _seed_scan,
        clear_all,
        lambda: not get_active_scan_id(),
    ),
    (
        "set_snapshot",
        _noop,
        lambda: set_snapshot({"active": True, "comics": []}),
        lambda: get_snapshot() is not None,
    ),
    (
        "clear_snapshot",
        _seed_snapshot,
        clear_snapshot,
        lambda: get_snapshot() is None,
    ),
    (
        "deactivate_snapshot",
        _seed_snapshot,
        deactivate_snapshot,
        _snapshot_inactive,
    ),
    (
        "record_resolution",
        _noop,
        lambda: record_resolution(1, USER_MATCHED, "metron"),
        lambda: 1 in get_resolved_outcomes(),
    ),
    (
        "set_resolved_outcomes",
        _noop,
        lambda: set_resolved_outcomes({1: USER_MATCHED}),
        lambda: 1 in get_resolved_outcomes(),
    ),
    (
        "clear_resolved_outcomes",
        _seed_resolution,
        clear_resolved_outcomes,
        lambda: not get_resolved_outcomes(),
    ),
    (
        "set_resume_state",
        _noop,
        lambda: set_resume_state({}, [1]),
        lambda: get_resume_state() is not None,
    ),
    (
        "clear_resume_state",
        _seed_resume,
        clear_resume_state,
        lambda: get_resume_state() is None,
    ),
)


class TaggingStateLockTests(SimpleTestCase):
    """Each writer blocks while another thread holds the state lock."""

    @override
    def setUp(self) -> None:
        caches["tagging"].clear()

    def test_every_writer_waits_for_the_lock(self) -> None:
        for name, seed, write, landed in _WRITERS:
            with self.subTest(name):
                caches["tagging"].clear()
                seed()
                with TAGGING_STATE_LOCK:
                    writer = Thread(target=write)
                    writer.start()
                    writer.join(timeout=_BLOCKED_WAIT_S)
                    assert writer.is_alive(), f"{name} wrote without the lock"
                    assert not landed()
                writer.join(timeout=5)
                assert landed()
