"""Unit tests for Janitor.cleanup_tagging_state."""

from multiprocessing import Event
from threading import Lock
from typing import override

from django.test import TestCase
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.models.admin import ComicboxTaggingDefaults


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


def _row() -> ComicboxTaggingDefaults:
    return ComicboxTaggingDefaults.objects.get(pk=1)


class CleanupTaggingStateTests(TestCase):
    """cleanup_tagging_state behavior across the live/stale/orphan states."""

    @override
    def setUp(self) -> None:
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1,
            defaults={"active_session_id": "", "active_prompts": []},
        )

    def test_clears_stale_session_when_no_thread_reference(self) -> None:
        ComicboxTaggingDefaults.objects.filter(pk=1).update(
            active_session_id="abc",
            active_prompts=[{"fingerprint": "x"}],
        )

        _make_janitor(online_tag_thread=None).cleanup_tagging_state()

        row = _row()
        assert row.active_session_id == ""
        assert row.active_prompts == []

    def test_clears_stale_session_when_thread_reports_dead(self) -> None:
        ComicboxTaggingDefaults.objects.filter(pk=1).update(
            active_session_id="abc",
            active_prompts=[{"fingerprint": "x"}],
        )

        _make_janitor(
            online_tag_thread=_StubOnlineTagThread(live_session_ids=set())
        ).cleanup_tagging_state()

        row = _row()
        assert row.active_session_id == ""
        assert row.active_prompts == []

    def test_preserves_state_when_session_is_live(self) -> None:
        ComicboxTaggingDefaults.objects.filter(pk=1).update(
            active_session_id="abc",
            active_prompts=[{"fingerprint": "x"}],
        )

        _make_janitor(
            online_tag_thread=_StubOnlineTagThread(live_session_ids={"abc"})
        ).cleanup_tagging_state()

        row = _row()
        assert row.active_session_id == "abc"
        assert row.active_prompts == [{"fingerprint": "x"}]

    def test_clears_orphan_prompts_when_session_id_blank(self) -> None:
        ComicboxTaggingDefaults.objects.filter(pk=1).update(
            active_session_id="",
            active_prompts=[{"fingerprint": "y"}],
        )

        _make_janitor().cleanup_tagging_state()

        row = _row()
        assert row.active_session_id == ""
        assert row.active_prompts == []

    def test_noop_when_already_clean(self) -> None:
        _make_janitor().cleanup_tagging_state()

        row = _row()
        assert row.active_session_id == ""
        assert row.active_prompts == []

    def test_noop_when_row_does_not_exist(self) -> None:
        ComicboxTaggingDefaults.objects.filter(pk=1).delete()

        _make_janitor().cleanup_tagging_state()

        assert not ComicboxTaggingDefaults.objects.filter(pk=1).exists()
