"""
Unit tests for Janitor.cleanup_tagging_state.

Under the persistent-prompt model, prompts deliberately linger across restarts
with no live scan behind them, so the nightly sweep no longer clears
"orphan" prompts. It only drops prompts whose comic has been deleted and
clears an active-scan marker with no live scan behind it.
"""

import shutil
from multiprocessing import Event
from pathlib import Path
from threading import Lock
from typing import Final, override

from django.core.cache import caches
from django.test import TestCase
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.onlinetag.session_cache import (
    get_active_scan_id,
    get_pending_prompts,
    set_active_scan_id,
    set_pending_prompts,
)
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume

_TMP_DIR: Final = Path("/tmp/codex.tests.janitor.tagging")  # noqa: S108
_MISSING_PK: Final = 999_999


class _StubOnlineTagThread:
    """Stand-in for OnlineTagThread that reports a fixed live-scan set."""

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


def _prompt(pk: int, fingerprint: str) -> dict:
    return {"fingerprint": fingerprint, "pk": pk, "path": f"/c/{pk}.cbz"}


class CleanupTaggingStateTests(TestCase):
    """cleanup_tagging_state prunes dead prompts and stale scan markers only."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    @staticmethod
    def _make_comic() -> Comic:
        _TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(_TMP_DIR))
        publisher = Publisher.objects.create(name="P")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        path = _TMP_DIR / "c.cbz"
        path.touch()
        return Comic.objects.create(
            library=library,
            path=path,
            issue_number=1,
            name="c",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=1,
            file_type="CBZ",
        )

    def test_prunes_prompts_for_missing_comics(self) -> None:
        set_pending_prompts({"fp": _prompt(_MISSING_PK, "fp")})

        _make_janitor().cleanup_tagging_state()

        assert get_pending_prompts() == {}

    def test_keeps_prompts_for_existing_comics(self) -> None:
        comic = self._make_comic()
        set_pending_prompts({"fp": _prompt(comic.pk, "fp")})

        _make_janitor().cleanup_tagging_state()

        assert "fp" in get_pending_prompts()

    def test_prunes_only_the_dead_prompts(self) -> None:
        comic = self._make_comic()
        set_pending_prompts(
            {
                "live": _prompt(comic.pk, "live"),
                "dead": _prompt(_MISSING_PK, "dead"),
            }
        )

        _make_janitor().cleanup_tagging_state()

        remaining = get_pending_prompts()
        assert "live" in remaining
        assert "dead" not in remaining

    def test_clears_stale_scan_marker_when_thread_reports_dead(self) -> None:
        set_active_scan_id("scan-1")

        _make_janitor(
            online_tag_thread=_StubOnlineTagThread(live_session_ids=set())
        ).cleanup_tagging_state()

        assert get_active_scan_id() == ""

    def test_clears_scan_marker_when_no_thread_reference(self) -> None:
        set_active_scan_id("scan-1")

        _make_janitor(online_tag_thread=None).cleanup_tagging_state()

        assert get_active_scan_id() == ""

    def test_keeps_live_scan_marker(self) -> None:
        set_active_scan_id("scan-1")

        _make_janitor(
            online_tag_thread=_StubOnlineTagThread(live_session_ids={"scan-1"})
        ).cleanup_tagging_state()

        assert get_active_scan_id() == "scan-1"

    def test_noop_when_already_clean(self) -> None:
        _make_janitor().cleanup_tagging_state()

        assert get_active_scan_id() == ""
        assert get_pending_prompts() == {}
