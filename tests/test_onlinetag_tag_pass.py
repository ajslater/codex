"""
Unit tests for the online-tag pass runner and stored-id prepass.

One of the online tagging manager modules; the shared test doubles and the
comic factory live in ``tests.onlinetag_session_fakes``.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import override

import pytest
from django.test import TestCase
from django.utils.timezone import now, timedelta
from loguru import logger

from codex.models import Identifier, IdentifierSource
from tests.onlinetag_session_fakes import TMP_DIR, FakeQueue, double, make_comic


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

        state = double(
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
            double(logger),
            double(FakeQueue()),
            double(_FakeStatusController()),
            lambda _state: None,
            lambda _state: None,
        )

        # A wait abandoned by the raise must not outlive the pass: run_session
        # freezes this snapshot for the admin to keep looking at.
        runner.source_retry_at["comicvine"] = (
            now() + timedelta(seconds=300)
        ).timestamp()

        with pytest.raises(RuntimeError):
            runner.collect_results(state, [Path("/c/a.cbz")], flush_writes=True)

        # The status was finished despite the raise, and the live reference
        # was cleared so a stray event can't poke a finished status.
        assert len(finished) == 1
        assert runner.lookup_status is None
        assert runner.rate_limited is False
        assert runner.source_retry_at == {}

    def test_collect_results_clears_retry_deadlines_when_cancelled(self) -> None:
        """Pausing mid-wait must not leave the table counting down forever."""
        from codex.librarian.onlinetag.tag_pass_runner import TagPassRunner

        class _NoopStatusController:
            def start(self, _status, **_kwargs) -> None:
                pass

            def update(self, _status, **_kwargs) -> None:
                pass

            def finish(self, _status, **_kwargs) -> None:
                pass

        class _CancelledSession:
            def tag_many(self, paths):
                # comicbox aborts the retry sleep on cancel, so the deadline
                # it was serving is abandoned with time left on it.
                return iter([SimpleNamespace(path=p) for p in paths])

        state = double(
            SimpleNamespace(
                session=_CancelledSession(),
                cancelled=True,
                pending_paths=[],
                total_comics=0,
                completed_comics=0,
                path_to_pk={},
                collected_tags={},
                match_mode="auto",
                sources=("metron", "comicvine"),
                merge_all_sources=False,
            )
        )
        runner = TagPassRunner(
            double(logger),
            double(FakeQueue()),
            double(_NoopStatusController()),
            lambda _state: None,
            lambda _state: None,
        )
        runner.source_retry_at["comicvine"] = (
            now() + timedelta(seconds=300)
        ).timestamp()

        runner.collect_results(state, [Path("/c/a.cbz")])

        assert runner.source_retry_at == {}

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
        state = double(
            SimpleNamespace(
                completed_comics=0,
                total_comics=10,
                match_mode="auto",
                sources=("metron", "comicvine"),
                merge_all_sources=False,
            )
        )
        runner = TagPassRunner(
            double(logger),
            double(FakeQueue()),
            double(_NoopStatusController()),
            lambda _state: None,
            lambda _state: None,
        )
        runner.rate_limited = True
        # comicvine is still throttled while metron finishes this comic.
        cv_retry = (now() + timedelta(seconds=300)).timestamp()
        runner.source_retry_at["comicvine"] = cv_retry

        runner._advance_result_status(state, status)  # noqa: SLF001

        assert state.completed_comics == 1
        assert status.subtitle == ""
        assert status.retry_at is None
        assert status.eta is not None
        assert runner.rate_limited is False
        # One source finishing a comic says nothing about another's wait, so
        # comicvine's deadline survives instead of being wiped.
        assert runner.source_retry_at == {"comicvine": cv_retry}


class BuildStoredIdMapTests(TestCase):
    """build_stored_id_map reads stored issue ids in source-priority order."""

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    @staticmethod
    def _identifier(source_name: str, id_type: str, key: str) -> Identifier:
        source, _ = IdentifierSource.objects.get_or_create(name=source_name)
        return Identifier.objects.create(source=source, id_type=id_type, key=key)

    def test_maps_issue_ids_in_source_priority_order(self) -> None:
        """Issue ids parse (incl. comicvine long keys) and order by priority."""
        from codex.librarian.onlinetag.stored_id_prepass import build_stored_id_map

        comic = make_comic()
        comic.identifiers.add(
            self._identifier("metron", "comic", "123495"),
            self._identifier("comicvine", "comic", "4000-67890"),
            # A non-issue (series) identifier must be ignored.
            self._identifier("metron", "series", "9841"),
        )

        id_map = build_stored_id_map([comic.pk], ("comicvine", "metron"))

        assert id_map == {comic.pk: {"comicvine": 67890, "metron": 123495}}
        assert list(id_map[comic.pk]) == ["comicvine", "metron"]

    def test_ignores_unrequested_sources_and_missing_ids(self) -> None:
        """Only requested sources count; comics without an id are absent."""
        from codex.librarian.onlinetag.stored_id_prepass import build_stored_id_map

        comic = make_comic()
        comic.identifiers.add(self._identifier("comicvine", "comic", "4000-67890"))

        assert build_stored_id_map([comic.pk], ("metron",)) == {}
