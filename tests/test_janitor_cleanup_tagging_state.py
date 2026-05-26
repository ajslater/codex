"""Unit tests for Janitor.cleanup_tagging_state."""

from multiprocessing import Event
from threading import Lock
from typing import override

from django.core.cache import cache
from django.test import TestCase
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.onlinetag.session_cache import (
    clear_active_session,
    get_active_prompts,
    get_active_session_id,
    set_active_prompts,
    set_active_session_id,
)
from codex.librarian.scribe.janitor.janitor import Janitor


class _StubOnlineTagThread:
    """Stand-in for OnlineTagThread that reports a fixed live-session set."""

    def __init__(self, live_session_ids: set[str] | None = None) -> None:
        self._live = live_session_ids or set()

    def has_active_session(self, session_id: str) -> bool:
        return session_id in self._live


def _make_janitor(online_tag_thread=None) -> Janitor:
    return Janitor(
        logger,
        LIBRARIAN_QUEUE,
        Lock(),
        Event(),
        online_tag_thread=online_tag_thread,
    )


class CleanupTaggingStateTests(TestCase):
    """cleanup_tagging_state behavior across the live/stale/orphan states."""

    @override
    def setUp(self) -> None:
        # The session/prompt state moved to the Django cache. Wipe it
        # between tests so a leak from one case doesn't pollute the
        # next.
        cache.clear()

    def test_clears_stale_session_when_no_thread_reference(self) -> None:
        set_active_session_id("abc")
        set_active_prompts([{"fingerprint": "x"}])

        _make_janitor(online_tag_thread=None).cleanup_tagging_state()

        assert get_active_session_id() == ""
        assert get_active_prompts() == []

    def test_clears_stale_session_when_thread_reports_dead(self) -> None:
        set_active_session_id("abc")
        set_active_prompts([{"fingerprint": "x"}])

        _make_janitor(
            online_tag_thread=_StubOnlineTagThread(live_session_ids=set())
        ).cleanup_tagging_state()

        assert get_active_session_id() == ""
        assert get_active_prompts() == []

    def test_preserves_state_when_session_is_live(self) -> None:
        set_active_session_id("abc")
        set_active_prompts([{"fingerprint": "x"}])

        _make_janitor(
            online_tag_thread=_StubOnlineTagThread(live_session_ids={"abc"})
        ).cleanup_tagging_state()

        assert get_active_session_id() == "abc"
        assert get_active_prompts() == [{"fingerprint": "x"}]

    def test_clears_orphan_prompts_when_session_id_blank(self) -> None:
        clear_active_session()
        set_active_prompts([{"fingerprint": "y"}])

        _make_janitor().cleanup_tagging_state()

        assert get_active_session_id() == ""
        assert get_active_prompts() == []

    def test_noop_when_already_clean(self) -> None:
        _make_janitor().cleanup_tagging_state()

        assert get_active_session_id() == ""
        assert get_active_prompts() == []
