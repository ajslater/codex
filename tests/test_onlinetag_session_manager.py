"""
Unit tests for a scan run by the online tagging session manager.

``run_session`` runs Pass 1 and persists ambiguous matches as deferred
prompts, then returns without blocking. Answering those prompts is covered by
``test_onlinetag_prompt_resolution``; credential assembly by
``test_onlinetag_credentials``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from comicbox.events import (
    AutoWritten,
    FileFinished,
    RateLimited,
    SearchCompleted,
    SearchStarted,
)
from loguru import logger

from codex.librarian.onlinetag.session_cache import (
    get_active_scan_id,
    get_pending_prompts,
)
from codex.librarian.onlinetag.session_state import SessionState
from codex.librarian.onlinetag.tasks import BulkOnlineTagTask
from codex.models import Comic, Identifier, IdentifierSource
from tests.onlinetag_session_fakes import (
    FETCH_TARGET,
    PATCH_TARGET,
    FakeDP,
    FakePassRunner,
    FakeSession,
    OnlineTagSessionTestCase,
    double,
    make_comic,
)


class OnlineTagScanTests(OnlineTagSessionTestCase):
    """run_session persists prompts non-blockingly and never re-searches."""

    def _no_op_pass(self) -> None:
        """Stub out Pass 1: only the steps around it are under test."""
        self.manager._pass_runner = double(FakePassRunner())  # noqa: SLF001

    @staticmethod
    def _add_issue_id(comic: Comic, source_name: str, key: str) -> None:
        """Attach a stored issue-level identifier to ``comic``."""
        source, _ = IdentifierSource.objects.get_or_create(name=source_name)
        identifier = Identifier.objects.create(source=source, id_type="comic", key=key)
        comic.identifiers.add(identifier)

    def _capture_search_paths(self, captured: list) -> None:
        """Make the (mocked) search pass record the comics it's handed."""
        self.manager._pass_runner = double(  # noqa: SLF001
            FakePassRunner(lambda _state, paths, **_kw: captured.extend(paths))
        )

    def test_run_session_persists_prompts_and_returns(self) -> None:
        comic = make_comic()
        comic_path = Path(comic.path)
        FakeSession.deferred = [FakeDP(comic_path, "fp1", "metron")]
        self._no_op_pass()
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-1",
            sources=("metron",),
            mode="auto",
        )

        with patch(PATCH_TARGET, FakeSession):
            self.manager.run_session(task)

        prompts = get_pending_prompts()
        assert "fp1" in prompts
        assert prompts["fp1"]["pk"] == comic.pk
        # The scan released its marker (non-blocking; nothing lingers in-flight).
        assert get_active_scan_id() == ""

    def test_run_session_passes_source_order_to_session(self) -> None:
        """The task's source order (run priority) reaches OnlineSession verbatim."""
        comic = make_comic()
        self._no_op_pass()
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-order",
            sources=("comicvine", "metron"),
            mode="auto",
        )

        with patch(PATCH_TARGET, FakeSession):
            self.manager.run_session(task)

        assert FakeSession.last_kwargs["sources"] == ("comicvine", "metron")

    def test_run_session_prefetches_stored_id_and_skips_search(self) -> None:
        """A comic with a stored issue id is fetched by id, not searched."""
        comic = make_comic()
        self._add_issue_id(comic, "metron", "123495")
        searched: list = []
        self._capture_search_paths(searched)
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-prefetch",
            sources=("metron",),
            mode="auto",
        )
        captured_fetch: dict = {}

        def _fake_fetch(path, source, issue_id, _credentials, **_kwargs):  # noqa: ARG001
            captured_fetch.update(source=source, issue_id=issue_id)
            return {"series": "X"}

        with patch(PATCH_TARGET, FakeSession), patch(FETCH_TARGET, _fake_fetch):
            self.manager.run_session(task)

        # Fetched directly by the stored id (numeric), never searched.
        assert captured_fetch == {"source": "metron", "issue_id": 123495}
        assert searched == []
        writes = self.write_tasks()
        assert len(writes) == 1
        assert writes[0].per_comic_patches == {comic.pk: {"series": "X"}}

    def test_run_session_unresolved_stored_id_falls_back_to_search(self) -> None:
        """A stored id that doesn't resolve leaves the comic for the search pass."""
        comic = make_comic()
        self._add_issue_id(comic, "metron", "123495")
        searched: list = []
        self._capture_search_paths(searched)
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-fallback",
            sources=("metron",),
            mode="auto",
        )

        with (
            patch(PATCH_TARGET, FakeSession),
            patch(FETCH_TARGET, lambda *_a, **_k: None),
        ):
            self.manager.run_session(task)

        assert not self.write_tasks()
        assert searched == [Path(comic.path)]

    def test_run_session_passes_pinned_ids_to_session(self) -> None:
        """A pinned id per source reaches OnlineSession, which fetches it."""
        comic = make_comic()
        self._no_op_pass()
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-pinned",
            sources=("metron", "comicvine"),
            mode="auto",
            ids={"metron": 12345},
        )

        with patch(PATCH_TARGET, FakeSession):
            self.manager.run_session(task)

        assert FakeSession.last_kwargs["ids"] == {"metron": 12345}

    def test_run_session_pinned_ids_bypass_the_stored_id_prepass(self) -> None:
        """
        A pinned request keeps its comic in the session instead of prefetching.

        The prepass drops what it fetches out of the search set, which would
        leave the unpinned sources with nothing to search — the pinned and
        searched sources have to resolve in the same lookup to merge.
        """
        comic = make_comic()
        self._add_issue_id(comic, "metron", "123495")
        searched: list = []
        self._capture_search_paths(searched)
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-pinned-prepass",
            sources=("metron", "comicvine"),
            mode="auto",
            ids={"comicvine": 456},
        )
        fetch_calls: list = []

        with (
            patch(PATCH_TARGET, FakeSession),
            patch(FETCH_TARGET, lambda *a, **_k: fetch_calls.append(a)),
        ):
            self.manager.run_session(task)

        assert fetch_calls == []
        assert searched == [Path(comic.path)]
        assert not self.write_tasks()

    def test_run_session_pinned_ids_land_in_resume_params(self) -> None:
        """A paused pinned session resumes still pinned."""
        comic = make_comic()
        captured: list = []
        self.manager._pass_runner = double(  # noqa: SLF001
            FakePassRunner(
                lambda state, *_a, **_k: captured.append(state.resume_params)
            )
        )
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-pinned-resume",
            sources=("metron",),
            mode="auto",
            ids={"metron": 12345},
        )

        with patch(PATCH_TARGET, FakeSession):
            self.manager.run_session(task)

        assert captured
        assert captured[0]["ids"] == {"metron": 12345}

    def test_prefetch_keeps_comic_in_status_out_of_search_and_resume(self) -> None:
        """A prefetched comic shows as matched yet is excluded from Resume."""
        from codex.librarian.onlinetag.session_snapshot import remaining_pks

        comic = make_comic()
        self._add_issue_id(comic, "metron", "123495")
        path = Path(comic.path)
        comic_paths = {comic.pk: path}
        state = SessionState(
            session=double(FakeSession()),
            path_to_pk={path: comic.pk},
            sources=("metron",),
        )
        credentials = self.manager._build_credentials()  # noqa: SLF001
        assert credentials is not None  # configured in setUp
        assert credentials.metron_key == "t"
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="s",
            sources=("metron",),
            mode="auto",
        )

        with patch(FETCH_TARGET, lambda *_a, **_k: {"series": "X"}):
            self.manager._prefetch_stored_ids(  # noqa: SLF001
                state, comic_paths, task, credentials
            )

        # Dropped from the search set, kept in the status map.
        assert comic_paths == {}
        assert state.path_to_pk == {path: comic.pk}
        # Counted complete + matched, and excluded from a Resume re-run.
        assert state.completed_comics == 1
        assert path in state.stats.written_paths
        # Attributed to the source whose stored id won it, so the status table
        # shows Matched in that column instead of an unexplained blank row.
        assert state.stats.matched_source_by_path[path] == ["metron"]
        assert state.stats.source_status_by_path[path] == {"metron": "matched"}
        assert remaining_pks(state, set()) == []

    def test_run_session_never_prompts_skips_persistence(self) -> None:
        comic = make_comic()
        comic_path = Path(comic.path)
        # An ambiguous match is available, but "never" must not persist it.
        FakeSession.deferred = [FakeDP(comic_path, "fp1", "metron")]
        self._no_op_pass()
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-never",
            sources=("metron",),
            mode="auto",
            prompts_mode="never",
        )

        with patch(PATCH_TARGET, FakeSession):
            self.manager.run_session(task)

        # The session was built to skip inline rather than defer prompts.
        assert FakeSession.last_kwargs["defer_prompts"] is False
        # No ambiguous match was queued for later resolution.
        assert get_pending_prompts() == {}
        assert get_active_scan_id() == ""

    def test_run_session_logs_outcome_summary(self) -> None:
        comic = make_comic()
        comic_path = Path(comic.path)
        on_event = self.manager._on_event  # noqa: SLF001

        def _drive(_state, _paths, **_kwargs) -> None:
            # Stand in for comicbox emitting events as it tags the one comic.
            on_event(AutoWritten(path=comic_path, source="metron"))
            on_event(FileFinished(path=comic_path, outcome="written"))

        self.manager._pass_runner = double(FakePassRunner(_drive))  # noqa: SLF001
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-summary",
            sources=("metron",),
            mode="auto",
        )

        messages: list[str] = []
        sink_id = logger.add(messages.append, level="INFO", format="{message}")
        try:
            with patch(PATCH_TARGET, FakeSession):
                self.manager.run_session(task)
        finally:
            logger.remove(sink_id)

        summaries = [m for m in messages if "Online tag session finished" in m]
        assert len(summaries) == 1
        assert "matched 1 (metron 1)" in summaries[0]

    def test_mark_rate_limited_sets_retry_and_eta(self) -> None:
        """A rate-limit event arms the retry countdown and pushes eta out."""
        from codex.librarian.onlinetag.status import OnlineLookupStatus

        status = OnlineLookupStatus()
        state = SessionState(
            session=double(FakeSession()),
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
        # The per-source mirror the status table's strip and Waiting cells read.
        retry_at = self.manager._pass_runner.source_retry_at  # noqa: SLF001
        assert retry_at == {"comicvine": status.retry_at.timestamp()}

    def test_exhausted_retry_budget_drops_the_countdown(self) -> None:
        """A giving-up source stops claiming a retry that will never come."""
        from codex.librarian.onlinetag.status import OnlineLookupStatus

        status = OnlineLookupStatus()
        state = SessionState(
            session=double(FakeSession()),
            match_mode="auto",
            sources=("comicvine",),
            total_comics=10,
            completed_comics=2,
        )
        self.manager._pass_runner.source_retry_at["comicvine"] = 1.0  # noqa: SLF001
        # comicbox emits a final RateLimited with no delay once the budget's out.
        event = RateLimited(source="comicvine", retry_after_seconds=None)

        self.manager._mark_rate_limited(status, state, event)  # noqa: SLF001

        assert status.retry_at is None
        assert self.manager._pass_runner.source_retry_at == {}  # noqa: SLF001

    def test_rate_limit_eta_accounts_for_merge_all_sources(self) -> None:
        """The stalled eta uses the same pacing model as the running one."""
        from codex.librarian.onlinetag.status import OnlineLookupStatus

        state = SessionState(
            session=double(FakeSession()),
            match_mode="auto",
            sources=("metron", "comicvine"),
            total_comics=10,
            completed_comics=2,
            merge_all_sources=True,
        )
        event = RateLimited(source="comicvine", retry_after_seconds=30)

        target = "codex.librarian.onlinetag.session_manager.estimate_seconds"
        with patch(target, return_value=0.0) as mocked:
            self.manager._mark_rate_limited(  # noqa: SLF001
                OnlineLookupStatus(), state, event
            )

        # Merge-all runs every source per comic, so omitting the flag would
        # under-estimate the work left and shrink the eta mid-wait.
        assert mocked.call_args.kwargs["merge_all_sources"] is True

    def test_source_outcome_event_releases_its_retry_countdown(self) -> None:
        """A source that reported an outcome is provably back at work."""
        self.manager._pass_runner.source_retry_at.update(  # noqa: SLF001
            {"comicvine": 1.0, "metron": 2.0}
        )

        self.manager._on_event(SearchCompleted(source="comicvine"))  # noqa: SLF001

        # Only the reporting source is released; metron's wait is its own.
        assert self.manager._pass_runner.source_retry_at == {"metron": 2.0}  # noqa: SLF001

    def test_search_started_does_not_release_a_retry_countdown(self) -> None:
        """SearchStarted fires before the request — the wait may be ongoing."""
        self.manager._pass_runner.source_retry_at["comicvine"] = 1.0  # noqa: SLF001

        self.manager._on_event(SearchStarted(source="comicvine"))  # noqa: SLF001

        assert self.manager._pass_runner.source_retry_at == {"comicvine": 1.0}  # noqa: SLF001

    def test_unmatched_scan_result_is_not_batched(self) -> None:
        """Pass-1 must not write a comic whose lookup applied nothing new."""
        from codex.librarian.onlinetag.tag_pass_runner import TagPassRunner

        path = Path("/c/a.cbz")
        state = double(SimpleNamespace(path_to_pk={path: 1}, collected_tags={}))
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
