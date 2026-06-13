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

import pytest
from comicbox.events import AutoWritten, FileFinished, RateLimited
from django.core.cache import caches
from django.test import TestCase
from django.utils.timezone import now, timedelta
from loguru import logger

from codex.librarian.onlinetag.session_cache import (
    get_active_scan_id,
    get_pending_prompts,
    set_pending_prompts,
)
from codex.librarian.onlinetag.session_manager import OnlineTagSessionManager
from codex.librarian.onlinetag.session_state import SessionState
from codex.librarian.onlinetag.tasks import (
    BulkOnlineTagTask,
    OnlineTagPromptResponseTask,
)
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
        caches["default"].clear()
        caches["tagging"].clear()
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
            SimpleNamespace(collect_results=lambda *_args, **_kwargs: None)
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

    def test_run_session_passes_source_order_to_session(self) -> None:
        """The task's source order (run priority) reaches OnlineSession verbatim."""
        comic = _make_comic()
        self.manager._pass_runner = _double(  # noqa: SLF001
            SimpleNamespace(collect_results=lambda *_args, **_kwargs: None)
        )
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-order",
            sources=("comicvine", "metron"),
            mode="auto",
        )

        with patch(_PATCH_TARGET, _FakeSession):
            self.manager.run_session(task)

        assert _FakeSession.last_kwargs["sources"] == ("comicvine", "metron")

    def test_run_session_never_prompts_skips_persistence(self) -> None:
        comic = _make_comic()
        comic_path = Path(comic.path)
        # An ambiguous match is available, but "never" must not persist it.
        _FakeSession.deferred = [_FakeDP(comic_path, "fp1", "metron")]
        # No-op Pass 1: we only exercise the (skipped) persist step here.
        self.manager._pass_runner = _double(  # noqa: SLF001
            SimpleNamespace(collect_results=lambda *_args, **_kwargs: None)
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

    def test_run_session_logs_outcome_summary(self) -> None:
        comic = _make_comic()
        comic_path = Path(comic.path)
        on_event = self.manager._on_event  # noqa: SLF001

        def _drive(_state, _paths, **_kwargs) -> None:
            # Stand in for comicbox emitting events as it tags the one comic.
            on_event(AutoWritten(path=comic_path, source="metron"))
            on_event(FileFinished(path=comic_path, outcome="written"))

        self.manager._pass_runner = _double(  # noqa: SLF001
            SimpleNamespace(collect_results=_drive)
        )
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-summary",
            sources=("metron",),
            mode="auto",
        )

        messages: list[str] = []
        sink_id = logger.add(messages.append, level="INFO", format="{message}")
        try:
            with patch(_PATCH_TARGET, _FakeSession):
                self.manager.run_session(task)
        finally:
            logger.remove(sink_id)

        summaries = [m for m in messages if "Online tag session finished" in m]
        assert len(summaries) == 1
        assert "matched 1 (metron 1)" in summaries[0]

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
            SimpleNamespace(
                path=Path(comic_path), tags={"series": "X"}, error=None, matched=True
            )
        ]

        with patch(_PATCH_TARGET, _FakeSession):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        # Prompt consumed.
        assert get_pending_prompts() == {}
        # The replay session defers on a cache miss instead of falling
        # through to comicbox's interactive CLI prompt in the daemon.
        assert _FakeSession.last_kwargs["defer_prompts"] is True
        # A chosen index is pinned to a manual issue-id resolution.
        assert _FakeSession.preloaded == [("fp1", "manual", "metron:123", None)]
        # A single-comic write was enqueued.
        writes = [i for i in self.queue.items if isinstance(i, BulkTagWriteTask)]
        assert len(writes) == 1
        assert writes[0].comic_pks == frozenset({comic.pk})
        assert writes[0].per_comic_patches == {comic.pk: {"series": "X"}}

    def test_resolve_unmatched_result_does_not_write(self) -> None:
        """An unmatched replay (tags = merged existing metadata) writes nothing."""
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
            SimpleNamespace(
                path=Path(comic_path),
                tags={"series": "Existing"},
                error=None,
                matched=False,
            )
        ]

        with patch(_PATCH_TARGET, _FakeSession):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert not [i for i in self.queue.items if isinstance(i, BulkTagWriteTask)]

    def test_resolve_drifted_prompt_requeues_fresh_prompt(self) -> None:
        """A fingerprint miss on replay re-persists the fresh deferred prompt."""
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
        # The re-search produced a different candidate set: the preloaded
        # fingerprint misses and the session defers a fresh prompt instead.
        _FakeSession.deferred = [_FakeDP(Path(comic_path), "fp2", "metron")]
        _FakeSession.tag_results = [
            SimpleNamespace(
                path=Path(comic_path),
                tags={"series": "Existing"},
                error=None,
                matched=False,
            )
        ]

        with patch(_PATCH_TARGET, _FakeSession):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert not [i for i in self.queue.items if isinstance(i, BulkTagWriteTask)]
        prompts = get_pending_prompts()
        assert set(prompts) == {"fp2"}
        assert prompts["fp2"]["pk"] == comic.pk
        assert prompts["fp2"]["formats"] == ["COMIC_INFO"]

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

    def test_pending_prompts_survive_default_cache_clear(self) -> None:
        """Importer-finish / CRUD cache.clear() must not strand pending prompts."""
        set_pending_prompts(
            {"fp1": {"fingerprint": "fp1", "pk": 1, "path": "/c/1.cbz", "source": "x"}}
        )

        caches["default"].clear()

        assert "fp1" in get_pending_prompts()

    def _seed_prompt(self, comic) -> dict:
        prompt = {
            "fingerprint": "fp1",
            "pk": comic.pk,
            "path": str(comic.path),
            "source": "metron",
            "candidates": [{"issue_id": 123, "source": "metron"}],
            "mode": "auto",
            "formats": ["COMIC_INFO"],
            "delete_original": False,
        }
        set_pending_prompts({"fp1": prompt})
        return prompt

    def test_defer_prompt_response_removes_from_cache_and_defers_apply(self) -> None:
        """A mid-scan "choose" clears the cache now but defers the write."""
        comic = _make_comic()
        self._seed_prompt(comic)
        state = SessionState(
            session=_double(_FakeSession()), path_to_pk={Path(comic.path): comic.pk}
        )
        task = OnlineTagPromptResponseTask(
            prompt_fingerprint="fp1", action="choose", payload=0
        )

        self.manager._defer_prompt_response(state, task)  # noqa: SLF001

        # Gone from the cache immediately, so a refresh won't resurrect it.
        assert get_pending_prompts() == {}
        assert "fp1" in state.answered_fingerprints
        # The network apply is deferred, not run inline mid-scan.
        assert len(state.deferred_applies) == 1
        assert not [i for i in self.queue.items if isinstance(i, BulkTagWriteTask)]

    def test_defer_prompt_response_skip_drops_without_deferring_apply(self) -> None:
        comic = _make_comic()
        self._seed_prompt(comic)
        state = SessionState(
            session=_double(_FakeSession()), path_to_pk={Path(comic.path): comic.pk}
        )
        task = OnlineTagPromptResponseTask(prompt_fingerprint="fp1", action="skip")

        self.manager._defer_prompt_response(state, task)  # noqa: SLF001

        assert get_pending_prompts() == {}
        assert "fp1" in state.answered_fingerprints
        assert state.deferred_applies == []

    def test_persist_prompts_skips_answered_fingerprints(self) -> None:
        """A scan must not re-persist a prompt the admin answered mid-scan."""
        comic = _make_comic()
        comic_path = Path(comic.path)
        _FakeSession.deferred = [_FakeDP(comic_path, "fp1", "metron")]
        state = SessionState(
            session=_double(_FakeSession()),
            path_to_pk={comic_path: comic.pk},
            formats=("COMIC_INFO",),
        )
        state.answered_fingerprints.add("fp1")

        self.manager._persist_prompts(state)  # noqa: SLF001

        assert get_pending_prompts() == {}

    def test_apply_deferred_resolutions_writes_then_clears(self) -> None:
        comic = _make_comic()
        comic_path = str(comic.path)
        prompt = self._seed_prompt(comic)
        # The cache entry was already removed inline; the apply re-fetches.
        set_pending_prompts({})
        _FakeSession.tag_results = [
            SimpleNamespace(
                path=Path(comic_path), tags={"series": "X"}, error=None, matched=True
            )
        ]
        state = SessionState(session=_double(_FakeSession()))
        state.deferred_applies.append((prompt, "choose", 0, None))

        with patch(_PATCH_TARGET, _FakeSession):
            self.manager._apply_deferred_resolutions(state)  # noqa: SLF001

        writes = [i for i in self.queue.items if isinstance(i, BulkTagWriteTask)]
        assert len(writes) == 1
        assert writes[0].per_comic_patches == {comic.pk: {"series": "X"}}
        assert state.deferred_applies == []

    def test_mark_rate_limited_sets_retry_and_eta(self) -> None:
        """A rate-limit event arms the retry countdown and pushes eta out."""
        from codex.librarian.onlinetag.status import OnlineLookupStatus

        status = OnlineLookupStatus()
        state = SessionState(
            session=_double(_FakeSession()),
            match_mode="auto",
            sources=("comicvine",),
            total_comics=10,
            completed_comics=2,
        )
        event = RateLimited(source="comicvine", retry_after_seconds=30)

        self.manager._mark_rate_limited(status, state, event)  # noqa: SLF001

        assert status.subtitle == "rate limited by comicvine"
        assert status.retry_at is not None
        assert status.eta is not None
        # eta = wait + remaining work, so it's strictly later than the retry.
        assert status.eta > status.retry_at

    def test_unmatched_scan_result_is_not_batched(self) -> None:
        """Pass-1 must not write a comic whose lookup applied nothing new."""
        from codex.librarian.onlinetag.tag_pass_runner import TagPassRunner

        path = Path("/c/a.cbz")
        state = _double(SimpleNamespace(path_to_pk={path: 1}, collected_tags={}))
        batch: dict = {}
        unmatched = SimpleNamespace(
            path=path, tags={"series": "Existing"}, error=None, matched=False
        )
        TagPassRunner._store_result_tags(state, unmatched, batch, flush_writes=True)  # noqa: SLF001
        assert batch == {}

        matched = SimpleNamespace(
            path=path, tags={"series": "New"}, error=None, matched=True
        )
        TagPassRunner._store_result_tags(state, matched, batch, flush_writes=True)  # noqa: SLF001
        assert batch == {1: {"series": "New"}}


class TagPassRunnerFinishTests(TestCase):
    """collect_results must always finish its status, even when a pass raises."""

    def test_collect_results_finishes_status_on_error(self) -> None:
        """A raise mid-pass must not strand the status row (frozen forever)."""
        from codex.librarian.onlinetag.tag_pass_runner import TagPassRunner

        finished: list = []

        class _FakeStatusController:
            def start(self, _status, **_kwargs) -> None:
                pass

            def update(self, _status, **_kwargs) -> None:
                pass

            def finish(self, status, **_kwargs) -> None:
                finished.append(status)

        class _BoomSession:
            def tag_many(self, _paths):
                msg = "rate-limit budget exhausted"
                raise RuntimeError(msg)

        state = _double(
            SimpleNamespace(
                session=_BoomSession(),
                cancelled=False,
                pending_paths=[],
                total_comics=0,
                completed_comics=0,
                path_to_pk={},
                collected_tags={},
                match_mode="auto",
                sources=("metron",),
                merge_all_sources=False,
            )
        )
        runner = TagPassRunner(
            _double(logger),
            _double(_FakeQueue()),
            _double(_FakeStatusController()),
            lambda _state: None,
        )

        with pytest.raises(RuntimeError):
            runner.collect_results(state, [Path("/c/a.cbz")], flush_writes=True)

        # The status was finished despite the raise, and the live reference
        # was cleared so a stray event can't poke a finished status.
        assert len(finished) == 1
        assert runner.lookup_status is None
        assert runner.rate_limited is False

    def test_advance_result_clears_retry_and_reestimates_eta(self) -> None:
        """A yielded result ends the wait and refreshes the time estimate."""
        from codex.librarian.onlinetag.status import OnlineLookupStatus
        from codex.librarian.onlinetag.tag_pass_runner import TagPassRunner

        class _NoopStatusController:
            def update(self, _status, **_kwargs) -> None:
                pass

        status = OnlineLookupStatus()
        status.subtitle = "rate limited by comicvine"
        status.retry_at = now() + timedelta(seconds=30)
        state = _double(
            SimpleNamespace(
                completed_comics=0,
                total_comics=10,
                match_mode="auto",
                sources=("metron",),
                merge_all_sources=False,
            )
        )
        runner = TagPassRunner(
            _double(logger),
            _double(_FakeQueue()),
            _double(_NoopStatusController()),
            lambda _state: None,
        )
        runner.rate_limited = True

        runner._advance_result_status(state, status)  # noqa: SLF001

        assert state.completed_comics == 1
        assert status.subtitle == ""
        assert status.retry_at is None
        assert status.eta is not None
        assert runner.rate_limited is False
