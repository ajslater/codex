"""
Unit tests for the non-blocking online tagging session manager.

A scan (``run_session``) runs Pass 1 and persists ambiguous matches as
deferred prompts, then returns without blocking. Answering a prompt
(``resolve_prompt``) is decoupled: it builds a fresh session, applies the
chosen match, and enqueues a single-comic write — no live scan required.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, Final, override
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from loguru import logger

from codex.librarian.onlinetag.session_cache import (
    get_active_scan_id,
    get_pending_prompts,
    set_pending_prompts,
)
from codex.librarian.onlinetag.session_manager import OnlineTagSessionManager
from codex.librarian.onlinetag.tasks import BulkOnlineTagTask
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import (
    Comic,
    ComicboxTaggingDefaults,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)

_TMP_DIR: Final = Path("/tmp/codex.tests.onlinetag.manager")  # noqa: S108
_PATCH_TARGET: Final = "codex.librarian.onlinetag.session_manager.OnlineSession"


def _double(stub: object) -> Any:
    """
    Pass a test double through a strictly-typed seam.

    The manager's constructor and ``_pass_runner`` attribute are annotated
    with concrete production types (loguru ``Logger``, multiprocessing
    ``Queue``, ``TagPassRunner``). These fakes only implement the slice the
    tests exercise, so erase to ``Any`` at the injection point instead of
    weakening the production annotations.
    """
    return stub


class _FakeQueue:
    """Collects everything put on it for assertions."""

    def __init__(self) -> None:
        self.items: list = []

    def put(self, item) -> None:
        self.items.append(item)


class _FakeCandidate:
    def __init__(self, issue_id: int, source: str) -> None:
        self.issue_id = issue_id
        self.source = source
        self.score = 0.9
        self.url = ""
        self.summary = SimpleNamespace(
            series="S", issue="1", year=2020, publisher="P", cover_url=""
        )


class _FakeDP:
    def __init__(self, path: Path, fingerprint: str, source: str) -> None:
        self.path = path
        self.fingerprint = fingerprint
        self.source = source
        self.mode = "auto"
        self.candidates = [_FakeCandidate(123, source)]


class _FakeSession:
    """Stand-in for comicbox.OnlineSession driven by class-level fixtures."""

    deferred: ClassVar[list] = []
    tag_results: ClassVar[list] = []
    preloaded: ClassVar[list] = []
    last_kwargs: ClassVar[dict] = {}

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        _FakeSession.last_kwargs = kwargs

    def tag_many(self, paths):  # noqa: ARG002
        return iter(_FakeSession.tag_results)

    def deferred_prompts(self):
        return list(_FakeSession.deferred)

    def preload_resolution(
        self, fingerprint, *, action, payload=None, chosen_volume_id=None
    ) -> None:
        _FakeSession.preloaded.append((fingerprint, action, payload, chosen_volume_id))

    def cancel(self) -> None:
        pass


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


class OnlineTagSessionManagerTests(TestCase):
    """run_session persists prompts non-blockingly; resolve applies via fresh session."""

    @override
    def setUp(self) -> None:
        cache.clear()
        _FakeSession.deferred = []
        _FakeSession.tag_results = []
        _FakeSession.preloaded = []
        _FakeSession.last_kwargs = {}
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1,
            defaults={"metron_user": "u", "metron_password": "p"},
        )
        self.queue = _FakeQueue()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.manager = OnlineTagSessionManager(  # pyright: ignore[reportUninitializedInstanceVariable]
            _double(logger),
            _double(self.queue),
            thread_queue=None,
        )

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_run_session_persists_prompts_and_returns(self) -> None:
        comic = _make_comic()
        comic_path = Path(comic.path)
        _FakeSession.deferred = [_FakeDP(comic_path, "fp1", "metron")]
        # No-op Pass 1: we only exercise the persist step here.
        self.manager._pass_runner = _double(  # noqa: SLF001
            SimpleNamespace(collect_results=lambda *a, **k: None)
        )
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-1",
            sources=("metron",),
            mode="auto",
        )

        with patch(_PATCH_TARGET, _FakeSession):
            self.manager.run_session(task)

        prompts = get_pending_prompts()
        assert "fp1" in prompts
        assert prompts["fp1"]["pk"] == comic.pk
        # The scan released its marker (non-blocking; nothing lingers in-flight).
        assert get_active_scan_id() == ""

    def test_run_session_never_prompts_skips_persistence(self) -> None:
        comic = _make_comic()
        comic_path = Path(comic.path)
        # An ambiguous match is available, but "never" must not persist it.
        _FakeSession.deferred = [_FakeDP(comic_path, "fp1", "metron")]
        # No-op Pass 1: we only exercise the (skipped) persist step here.
        self.manager._pass_runner = _double(  # noqa: SLF001
            SimpleNamespace(collect_results=lambda *a, **k: None)
        )
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-never",
            sources=("metron",),
            mode="auto",
            prompts_mode="never",
        )

        with patch(_PATCH_TARGET, _FakeSession):
            self.manager.run_session(task)

        # The session was built to skip inline rather than defer prompts.
        assert _FakeSession.last_kwargs["defer_prompts"] is False
        # No ambiguous match was queued for later resolution.
        assert get_pending_prompts() == {}
        assert get_active_scan_id() == ""

    def test_resolve_choose_applies_via_fresh_session_and_writes(self) -> None:
        comic = _make_comic()
        comic_path = str(comic.path)
        set_pending_prompts(
            {
                "fp1": {
                    "fingerprint": "fp1",
                    "pk": comic.pk,
                    "path": comic_path,
                    "source": "metron",
                    "candidates": [{"issue_id": 123, "source": "metron"}],
                    "mode": "auto",
                    "formats": ["COMIC_INFO"],
                    "delete_original": False,
                }
            }
        )
        _FakeSession.tag_results = [
            SimpleNamespace(path=Path(comic_path), tags={"series": "X"}, error=None)
        ]

        with patch(_PATCH_TARGET, _FakeSession):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        # Prompt consumed.
        assert get_pending_prompts() == {}
        # A chosen index is pinned to a manual issue-id resolution.
        assert _FakeSession.preloaded == [("fp1", "manual", "metron:123", None)]
        # A single-comic write was enqueued.
        writes = [i for i in self.queue.items if isinstance(i, BulkTagWriteTask)]
        assert len(writes) == 1
        assert writes[0].comic_pks == frozenset({comic.pk})
        assert writes[0].per_comic_patches == {comic.pk: {"series": "X"}}

    def test_resolve_skip_drops_prompt_without_writing(self) -> None:
        set_pending_prompts(
            {"fp1": {"fingerprint": "fp1", "pk": 1, "path": "/c/1.cbz", "source": "x"}}
        )

        with patch(_PATCH_TARGET, _FakeSession):
            self.manager.resolve_prompt("fp1", "skip", None, None)

        assert get_pending_prompts() == {}
        assert not [i for i in self.queue.items if isinstance(i, BulkTagWriteTask)]

    def test_skip_all_clears_every_prompt(self) -> None:
        seeded = {
            "a": {"fingerprint": "a", "pk": 1, "path": "/c/1.cbz", "source": "x"},
            "b": {"fingerprint": "b", "pk": 2, "path": "/c/2.cbz", "source": "x"},
        }
        set_pending_prompts(seeded)

        count = self.manager.skip_all_prompts()

        assert count == len(seeded)
        assert get_pending_prompts() == {}

    def test_resolve_unknown_prompt_is_a_noop(self) -> None:
        with patch(_PATCH_TARGET, _FakeSession):
            self.manager.resolve_prompt("nope", "choose", 0, None)

        assert not [i for i in self.queue.items if isinstance(i, BulkTagWriteTask)]
