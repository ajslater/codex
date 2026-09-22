"""
Unit tests for answering an online tagging prompt.

Resolution is decoupled from the scan that raised the prompt: ``resolve_prompt``
builds a fresh session, applies the chosen match, and enqueues a single-comic
write — no live scan required. A response that arrives *during* a scan is
deferred instead, and applied when the scan winds down.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Final
from unittest.mock import patch

import pytest
from django.core.cache import caches

from codex.librarian.onlinetag.session_cache import (
    get_pending_prompts,
    set_pending_prompts,
)
from codex.librarian.onlinetag.session_snapshot import get_resolved_outcomes
from codex.librarian.onlinetag.session_state import SessionState
from codex.librarian.onlinetag.statuses import USER_MATCHED
from codex.librarian.onlinetag.tasks import OnlineTagPromptResponseTask
from codex.librarian.scribe.tagwrite_errors import get_tag_write_errors
from tests.onlinetag_session_fakes import (
    APPLY_FETCH_TARGET,
    APPLY_SESSION_TARGET,
    FakeDP,
    FakeSession,
    OnlineTagSessionTestCase,
    double,
    make_comic,
    make_series_comics,
)


def _prompt(comic, *, path: str | None = None, candidates: list | None = None) -> dict:
    """Build a serialized deferred prompt for ``comic``, as the scan persists it."""
    return {
        "fingerprint": "fp1",
        "pk": comic.pk,
        "path": path if path is not None else str(comic.path),
        "source": "metron",
        "candidates": candidates
        if candidates is not None
        else [{"issue_id": 123, "source": "metron"}],
        "mode": "auto",
        "formats": ["COMIC_INFO"],
        "delete_original": False,
    }


class OnlineTagPromptResolutionTests(OnlineTagSessionTestCase):
    """A pick is fetched by id and written; a replay may drift or write nothing."""

    def test_resolve_choose_fetches_chosen_issue_by_id_and_writes(self) -> None:
        """A pick is fetched by its exact issue id, not re-searched."""
        comic = make_comic()
        comic_path = str(comic.path)
        set_pending_prompts({"fp1": _prompt(comic)})
        captured: dict = {}

        def _fake_fetch(path, source, issue_id, _credentials, **_kwargs):
            captured.update(path=str(path), source=source, issue_id=issue_id)
            return {"series": "X"}

        with patch(APPLY_FETCH_TARGET, _fake_fetch):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        # Prompt consumed; the exact chosen issue was fetched directly by id.
        assert get_pending_prompts() == {}
        assert captured == {"path": comic_path, "source": "metron", "issue_id": 123}
        # The replay session was never built — no re-search to drift.
        assert FakeSession.preloaded == []
        # A single-comic write was enqueued, and the outcome recorded.
        writes = self.write_tasks()
        assert len(writes) == 1
        assert writes[0].comic_pks == frozenset({comic.pk})
        assert writes[0].per_comic_patches == {comic.pk: {"series": "X"}}
        # Recorded against the source that prompted, so the status table can
        # show the outcome in that source's column.
        assert get_resolved_outcomes().get(comic.pk) == {
            "status": USER_MATCHED,
            "sources": {"metron": USER_MATCHED},
        }

    def test_resolve_choose_unresolved_id_does_not_write_or_requeue(self) -> None:
        """A pick whose id doesn't resolve writes nothing and never re-prompts."""
        comic = make_comic()
        set_pending_prompts({"fp1": _prompt(comic)})

        with patch(APPLY_FETCH_TARGET, lambda *_a, **_k: None):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert not self.write_tasks()
        # The explicit choice is honored: no worse fresh prompt is re-queued.
        assert get_pending_prompts() == {}
        # The consumed-but-unapplied pick surfaces on the admin error panel.
        errors = get_tag_write_errors()
        assert len(errors) == 1
        assert "did not resolve" in errors[0]["error"]

    def test_resolve_fetches_against_current_db_path_not_prompt_snapshot(self) -> None:
        """
        A pick applies against the comic's current DB path, not the prompt's.

        The serialized prompt path goes stale when an earlier write for the
        same comic ran with rename enabled (e.g. the comic's other source's
        prompt was answered first) — the DB row follows the rename.
        """
        comic = make_comic()
        stale_path = str(Path(comic.path).with_name("stale-pre-rename-name.cbz"))
        set_pending_prompts({"fp1": _prompt(comic, path=stale_path)})
        captured: dict = {}

        def _fake_fetch(path, source, issue_id, _credentials, **_kwargs):
            captured.update(path=str(path), source=source, issue_id=issue_id)
            return {"series": "X"}

        with patch(APPLY_FETCH_TARGET, _fake_fetch):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert captured["path"] == str(comic.path)
        writes = self.write_tasks()
        assert len(writes) == 1
        assert writes[0].comic_pks == frozenset({comic.pk})

    def test_resolve_fetch_failure_surfaces_error_without_crashing(self) -> None:
        """A fetch crash (stale file, source error) reports; the pick isn't lost silently."""
        comic = make_comic()
        comic_path = str(comic.path)
        prompt = _prompt(
            comic, candidates=[{"issue_id": 764978, "source": "comicvine"}]
        )
        prompt["source"] = "comicvine"
        set_pending_prompts({"fp1": prompt})

        def _boom(*_args, **_kwargs):
            reason = f"{comic_path} does not exist."
            raise FileNotFoundError(reason)

        with patch(APPLY_FETCH_TARGET, _boom):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert not self.write_tasks()
        assert get_pending_prompts() == {}
        errors = get_tag_write_errors()
        assert len(errors) == 1
        assert "fetching chosen issue comicvine:764978 failed" in errors[0]["error"]

    def test_resolve_missing_comic_row_reports_and_never_fetches(self) -> None:
        """A prompt whose comic left the DB reports instead of fetching a dead path."""
        gone = SimpleNamespace(pk=999_999, path="/gone/c.cbz")
        set_pending_prompts({"fp1": _prompt(gone)})
        called: list = []

        def _fake_fetch(*args, **_kwargs):
            called.append(args)
            return {"series": "X"}

        with patch(APPLY_FETCH_TARGET, _fake_fetch):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert not called
        assert not self.write_tasks()
        errors = get_tag_write_errors()
        assert len(errors) == 1
        assert "no longer in the database" in errors[0]["error"]

    def test_resolve_drifted_prompt_requeues_fresh_prompt(self) -> None:
        """A candidate with no issue id falls back to replay, which can drift."""
        comic = make_comic()
        comic_path = str(comic.path)
        # No issue_id → not an explicit pick → replay path.
        set_pending_prompts({"fp1": _prompt(comic, candidates=[{"source": "metron"}])})
        # The re-search produced a different candidate set: the preloaded
        # fingerprint misses and the session defers a fresh prompt instead.
        FakeSession.deferred = [FakeDP(Path(comic_path), "fp2", "metron")]
        FakeSession.tag_results = [
            SimpleNamespace(
                path=Path(comic_path),
                tags={"series": "Existing"},
                error=None,
                matched=False,
            )
        ]

        with patch(APPLY_SESSION_TARGET, FakeSession):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert not self.write_tasks()
        prompts = get_pending_prompts()
        assert set(prompts) == {"fp2"}
        assert prompts["fp2"]["pk"] == comic.pk
        assert prompts["fp2"]["formats"] == ["COMIC_INFO"]

    def test_resolve_unmatched_result_does_not_write(self) -> None:
        """An unmatched replay (tags = merged existing metadata) writes nothing."""
        comic = make_comic()
        # No issue_id → not an explicit pick → replay path.
        set_pending_prompts({"fp1": _prompt(comic, candidates=[{"source": "metron"}])})
        FakeSession.tag_results = [
            SimpleNamespace(
                path=Path(comic.path),
                tags={"series": "Existing"},
                error=None,
                matched=False,
            )
        ]

        with patch(APPLY_SESSION_TARGET, FakeSession):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert not self.write_tasks()

    def test_resolve_skip_drops_prompt_without_writing(self) -> None:
        set_pending_prompts(
            {"fp1": {"fingerprint": "fp1", "pk": 1, "path": "/c/1.cbz", "source": "x"}}
        )

        with patch(APPLY_SESSION_TARGET, FakeSession):
            self.manager.resolve_prompt("fp1", "skip", None, None)

        assert get_pending_prompts() == {}
        assert not self.write_tasks()

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
        with patch(APPLY_SESSION_TARGET, FakeSession):
            self.manager.resolve_prompt("nope", "choose", 0, None)

        assert not self.write_tasks()

    def test_pending_prompts_survive_default_cache_clear(self) -> None:
        """Importer-finish / CRUD cache.clear() must not strand pending prompts."""
        set_pending_prompts(
            {"fp1": {"fingerprint": "fp1", "pk": 1, "path": "/c/1.cbz", "source": "x"}}
        )

        caches["default"].clear()

        assert "fp1" in get_pending_prompts()


class OnlineTagMidScanResponseTests(OnlineTagSessionTestCase):
    """A response that lands mid-scan clears the prompt now and writes later."""

    @staticmethod
    def _seed_prompt(comic) -> dict:
        prompt = _prompt(comic)
        set_pending_prompts({"fp1": prompt})
        return prompt

    def test_defer_prompt_response_removes_from_cache_and_defers_apply(self) -> None:
        """A mid-scan "choose" clears the cache now but defers the write."""
        comic = make_comic()
        self._seed_prompt(comic)
        state = SessionState(
            session=double(FakeSession()), path_to_pk={Path(comic.path): comic.pk}
        )
        task = OnlineTagPromptResponseTask(
            prompt_fingerprint="fp1", action="choose", payload=0
        )

        self.manager._defer_prompt_response(state, task)  # noqa: SLF001

        # Gone from the cache immediately, so a refresh won't resurrect it.
        assert get_pending_prompts() == {}
        assert comic.pk in state.answered_pks
        # The network apply is deferred, not run inline mid-scan.
        assert len(state.deferred_applies) == 1
        assert not self.write_tasks()

    def test_defer_prompt_response_skip_drops_without_deferring_apply(self) -> None:
        comic = make_comic()
        self._seed_prompt(comic)
        state = SessionState(
            session=double(FakeSession()), path_to_pk={Path(comic.path): comic.pk}
        )
        task = OnlineTagPromptResponseTask(prompt_fingerprint="fp1", action="skip")

        self.manager._defer_prompt_response(state, task)  # noqa: SLF001

        assert get_pending_prompts() == {}
        assert comic.pk in state.answered_pks
        assert state.deferred_applies == []

    def test_persist_prompts_skips_answered_comics(self) -> None:
        """A scan must not re-persist a prompt the admin answered mid-scan."""
        comic = make_comic()
        comic_path = Path(comic.path)
        FakeSession.deferred = [FakeDP(comic_path, "fp1", "metron")]
        state = SessionState(
            session=double(FakeSession()),
            path_to_pk={comic_path: comic.pk},
            formats=("COMIC_INFO",),
        )
        state.answered_pks.add(comic.pk)

        self.manager._persist_prompts(state)  # noqa: SLF001

        assert get_pending_prompts() == {}

    def test_apply_deferred_resolutions_writes_then_clears(self) -> None:
        comic = make_comic()
        prompt = self._seed_prompt(comic)
        # The cache entry was already removed inline; the apply re-fetches.
        set_pending_prompts({})
        state = SessionState(session=double(FakeSession()))
        state.deferred_applies.append((prompt, "choose", 0, None))

        with patch(APPLY_FETCH_TARGET, lambda *_a, **_k: {"series": "X"}):
            self.manager._apply_deferred_resolutions(state)  # noqa: SLF001

        writes = self.write_tasks()
        assert len(writes) == 1
        assert writes[0].per_comic_patches == {comic.pk: {"series": "X"}}
        assert state.deferred_applies == []


def _series_prompt(comics, *, candidates: list | None = None) -> dict:
    """Build the one series-level prompt comicbox raises for several issues."""
    return {
        **_prompt(comics[0], candidates=candidates),
        "comics": [{"pk": c.pk, "path": str(c.path)} for c in comics],
    }


class OnlineTagSeriesPromptTests(OnlineTagSessionTestCase):
    """
    One answer covers every issue of the series that asked the question.

    Comicbox fingerprints a deferred prompt at series level so a single pick
    answers a whole run. Codex used to keep only the last comic to defer under
    a fingerprint, so every other issue was silently dropped: never prompted,
    never written, and left showing "needs review" with nothing to press.
    """

    @staticmethod
    def _matched_result(path) -> SimpleNamespace:
        """Build a replay result that found the picked volume's issue."""
        return SimpleNamespace(
            path=Path(path), tags={"series": "S"}, error=None, matched=True
        )

    def test_resolve_applies_the_pick_to_every_issue_of_the_series(self) -> None:
        """The representative is fetched by id; the rest replay into the volume."""
        comics = make_series_comics(3)
        set_pending_prompts({"fp1": _series_prompt(comics)})
        FakeSession.tag_results = [self._matched_result(comics[1].path)]

        with (
            patch(APPLY_SESSION_TARGET, FakeSession),
            patch(APPLY_FETCH_TARGET, lambda *_a, **_k: {"series": "S"}),
        ):
            self.manager.resolve_prompt("fp1", "choose", 0, 55)

        written = set()
        for task in self.write_tasks():
            written.update(task.per_comic_patches)
        assert written == {c.pk for c in comics}
        # The followers replayed with the admin's volume preloaded, so their
        # own issue numbers resolve inside it rather than taking issue #1.
        assert [p[1] for p in FakeSession.preloaded] == ["choose", "choose"]
        assert {p[3] for p in FakeSession.preloaded} == {55}

    def test_resolve_records_the_outcome_for_every_issue(self) -> None:
        """Every row of the series leaves review, not just the one shown."""
        comics = make_series_comics(3)
        set_pending_prompts({"fp1": _series_prompt(comics)})
        FakeSession.tag_results = [self._matched_result(comics[1].path)]

        with (
            patch(APPLY_SESSION_TARGET, FakeSession),
            patch(APPLY_FETCH_TARGET, lambda *_a, **_k: {"series": "S"}),
        ):
            self.manager.resolve_prompt("fp1", "choose", 0, 55)

        outcomes = get_resolved_outcomes()
        for comic in comics:
            assert outcomes[comic.pk]["status"] == USER_MATCHED

    def test_a_pick_with_no_volume_requeues_the_rest_of_the_series(self) -> None:
        """
        An untransferable pick writes one comic and re-asks for the others.

        Without a volume id there is nothing to narrow the other issues'
        lookups with — the candidates were scored for one issue — so the
        honest move is another question, not writing one issue's match onto
        the whole series.
        """
        comics = make_series_comics(3)
        set_pending_prompts({"fp1": _series_prompt(comics)})

        with (
            patch(APPLY_SESSION_TARGET, FakeSession),
            patch(APPLY_FETCH_TARGET, lambda *_a, **_k: {"series": "S"}),
        ):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        writes = self.write_tasks()
        assert len(writes) == 1
        assert set(writes[0].per_comic_patches) == {comics[0].pk}
        requeued = get_pending_prompts()["fp1"]
        assert [c["pk"] for c in requeued["comics"]] == [comics[1].pk, comics[2].pk]
        # The re-queued question's representative is one of the comics still
        # waiting, so answering it again can't re-apply to the comic just done.
        assert requeued["pk"] == comics[1].pk

    def test_skip_covers_every_issue_of_the_series(self) -> None:
        """Skipping the question skips every comic waiting on it."""
        comics = make_series_comics(2)
        set_pending_prompts({"fp1": _series_prompt(comics)})

        with patch(APPLY_SESSION_TARGET, FakeSession):
            self.manager.resolve_prompt("fp1", "skip", None, None)

        outcomes = get_resolved_outcomes()
        assert {c.pk for c in comics} <= set(outcomes)
        assert not self.write_tasks()

    def test_a_mid_scan_answer_reaches_the_running_session(self) -> None:
        """
        The pick is preloaded so the scan resolves the rest of the series itself.

        This is comicbox's half of the deferred-prompt contract: a series-level
        fingerprint is only useful if the answer goes back in, and skipping it
        is why later issues re-deferred a question nobody could answer.
        """
        comics = make_series_comics(2)
        set_pending_prompts({"fp1": _series_prompt(comics)})
        state = SessionState(
            session=double(FakeSession()),
            path_to_pk={Path(c.path): c.pk for c in comics},
        )
        task = OnlineTagPromptResponseTask(
            prompt_fingerprint="fp1", action="choose", payload=0, chosen_volume_id=55
        )

        self.manager._defer_prompt_response(state, task)  # noqa: SLF001

        assert FakeSession.preloaded == [("fp1", "choose", 0, 55)]
        assert state.answered_pks == {c.pk for c in comics}

    def test_a_later_issue_of_an_answered_series_still_gets_asked(self) -> None:
        """
        Answering issue 1 must not silence issue 5's own question.

        The suppression used to key on the fingerprint, which a whole series
        shares — so every issue that deferred after the answer was thrown away
        instead of queued.
        """
        answered, later = make_series_comics(2)
        state = SessionState(
            session=double(FakeSession()),
            path_to_pk={Path(answered.path): answered.pk, Path(later.path): later.pk},
            formats=("COMIC_INFO",),
        )
        state.answered_pks.add(answered.pk)
        FakeSession.deferred = [
            FakeDP(Path(answered.path), "fp1", "metron"),
            FakeDP(Path(later.path), "fp1", "metron"),
        ]

        self.manager._persist_prompts(state)  # noqa: SLF001

        prompts = get_pending_prompts()
        assert [c["pk"] for c in prompts["fp1"]["comics"]] == [later.pk]


_COMICVINE_MODULE: Final = "comicbox.formats.comicvine_api.online_source"
_RELEASE_TARGET: Final = (
    "comicbox.formats.metron_api.online_source.close_shared_sessions"
)
_COMICVINE_RELEASE_TARGET: Final = f"{_COMICVINE_MODULE}.close_shared_sessions"


class PromptResolutionConnectionReleaseTests(OnlineTagSessionTestCase):
    """
    Answering a prompt hands back what it opened.

    The applier builds its own session per answer, so nothing else will
    close it. Skipping makes no request at all, so it must not pay for a
    reconnect on the next answer. Since comicbox 5.2.1 the release
    covers Comic Vine as well as Metron.
    """

    def test_an_applied_answer_releases_once(self) -> None:
        comic = make_comic()
        set_pending_prompts({"fp1": _prompt(comic)})

        def _fake_fetch(_path, _source, _issue_id, _credentials, **_kwargs):
            return {"series": "X"}

        with (
            patch(APPLY_FETCH_TARGET, _fake_fetch),
            patch(_RELEASE_TARGET) as release,
        ):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        release.assert_called_once_with()

    def test_an_applier_that_raises_still_releases(self) -> None:
        comic = make_comic()
        set_pending_prompts({"fp1": _prompt(comic)})

        def _boom(*_args, **_kwargs):
            msg = "apply died"
            raise RuntimeError(msg)

        with (
            patch.object(type(self.manager._prompt_applier), "apply", _boom),  # noqa: SLF001
            patch(_RELEASE_TARGET) as release,
            pytest.raises(RuntimeError, match="apply died"),
        ):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        release.assert_called_once_with()

    def test_a_skipped_prompt_releases_nothing(self) -> None:
        set_pending_prompts(
            {"fp1": {"fingerprint": "fp1", "pk": 1, "path": "/c/1.cbz", "source": "x"}}
        )

        with (
            patch(APPLY_SESSION_TARGET, FakeSession),
            patch(_RELEASE_TARGET) as release,
        ):
            self.manager.resolve_prompt("fp1", "skip", None, None)

        release.assert_not_called()

    def test_an_applied_answer_releases_both_sources(self) -> None:
        """A Comic Vine answer leaves no sockets or sqlite handles behind."""
        comic = make_comic()
        set_pending_prompts({"fp1": _prompt(comic)})

        def _fake_fetch(_path, _source, _issue_id, _credentials, **_kwargs):
            return {"series": "X"}

        with (
            patch(APPLY_FETCH_TARGET, _fake_fetch),
            patch(_RELEASE_TARGET) as metron_release,
            patch(_COMICVINE_RELEASE_TARGET) as comicvine_release,
        ):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        metron_release.assert_called_once_with()
        comicvine_release.assert_called_once_with()

    def test_a_skipped_prompt_releases_neither_source(self) -> None:
        """The skip branch returns before the release, having made no request."""
        set_pending_prompts(
            {"fp1": {"fingerprint": "fp1", "pk": 1, "path": "/c/1.cbz", "source": "x"}}
        )

        with (
            patch(APPLY_SESSION_TARGET, FakeSession),
            patch(_RELEASE_TARGET) as metron_release,
            patch(_COMICVINE_RELEASE_TARGET) as comicvine_release,
        ):
            self.manager.resolve_prompt("fp1", "skip", None, None)

        metron_release.assert_not_called()
        comicvine_release.assert_not_called()
