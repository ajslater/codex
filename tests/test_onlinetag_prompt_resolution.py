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
from unittest.mock import patch

from django.core.cache import caches

from codex.librarian.onlinetag.session_cache import (
    get_pending_prompts,
    set_pending_prompts,
)
from codex.librarian.onlinetag.session_snapshot import (
    USER_MATCHED,
    get_resolved_outcomes,
)
from codex.librarian.onlinetag.session_state import SessionState
from codex.librarian.onlinetag.tasks import OnlineTagPromptResponseTask
from codex.librarian.scribe.tagwrite_errors import get_tag_write_errors
from tests.onlinetag_session_fakes import (
    FETCH_TARGET,
    PATCH_TARGET,
    FakeDP,
    FakeSession,
    OnlineTagSessionTestCase,
    double,
    make_comic,
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

        with patch(FETCH_TARGET, _fake_fetch):
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
        assert get_resolved_outcomes().get(comic.pk) == USER_MATCHED

    def test_resolve_choose_unresolved_id_does_not_write_or_requeue(self) -> None:
        """A pick whose id doesn't resolve writes nothing and never re-prompts."""
        comic = make_comic()
        set_pending_prompts({"fp1": _prompt(comic)})

        with patch(FETCH_TARGET, lambda *_a, **_k: None):
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

        with patch(FETCH_TARGET, _fake_fetch):
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

        with patch(FETCH_TARGET, _boom):
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

        with patch(FETCH_TARGET, _fake_fetch):
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

        with patch(PATCH_TARGET, FakeSession):
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

        with patch(PATCH_TARGET, FakeSession):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert not self.write_tasks()

    def test_resolve_skip_drops_prompt_without_writing(self) -> None:
        set_pending_prompts(
            {"fp1": {"fingerprint": "fp1", "pk": 1, "path": "/c/1.cbz", "source": "x"}}
        )

        with patch(PATCH_TARGET, FakeSession):
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
        with patch(PATCH_TARGET, FakeSession):
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
        assert "fp1" in state.answered_fingerprints
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
        assert "fp1" in state.answered_fingerprints
        assert state.deferred_applies == []

    def test_persist_prompts_skips_answered_fingerprints(self) -> None:
        """A scan must not re-persist a prompt the admin answered mid-scan."""
        comic = make_comic()
        comic_path = Path(comic.path)
        FakeSession.deferred = [FakeDP(comic_path, "fp1", "metron")]
        state = SessionState(
            session=double(FakeSession()),
            path_to_pk={comic_path: comic.pk},
            formats=("COMIC_INFO",),
        )
        state.answered_fingerprints.add("fp1")

        self.manager._persist_prompts(state)  # noqa: SLF001

        assert get_pending_prompts() == {}

    def test_apply_deferred_resolutions_writes_then_clears(self) -> None:
        comic = make_comic()
        prompt = self._seed_prompt(comic)
        # The cache entry was already removed inline; the apply re-fetches.
        set_pending_prompts({})
        state = SessionState(session=double(FakeSession()))
        state.deferred_applies.append((prompt, "choose", 0, None))

        with patch(FETCH_TARGET, lambda *_a, **_k: {"series": "X"}):
            self.manager._apply_deferred_resolutions(state)  # noqa: SLF001

        writes = self.write_tasks()
        assert len(writes) == 1
        assert writes[0].per_comic_patches == {comic.pk: {"series": "X"}}
        assert state.deferred_applies == []
