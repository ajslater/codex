"""
Two prompts on one comic, answered back to back, keep the run's merge order.

The first answer's write is only queued when the second is applied, so the
database does not have its issue id yet. These tests run comicbox's real
merge on a real archive, with fake online sources standing in for the APIs.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Final, override
from unittest.mock import patch

from django.test import SimpleTestCase

from codex.librarian.notifier.tasks import ONLINE_TAG_PROMPT_TASK
from codex.librarian.onlinetag.session_cache import (
    get_pending_prompts,
    note_tagged_ids,
    set_pending_prompts,
)
from codex.librarian.onlinetag.session_state import SessionState
from codex.models import ComicboxTaggingDefaults
from tests.onlinetag_merge_fakes import (
    COMICVINE_ID,
    METRON_ID,
    VOLUME_ID,
    answer,
    comic_entry,
    fake_sources,
    make_prompt,
    replayed,
    write_archive,
)
from tests.onlinetag_session_fakes import (
    APPLY_SESSION_TARGET,
    FakeDP,
    FakeSession,
    OnlineTagSessionTestCase,
    double,
    make_comic,
    make_series_comics,
)

if TYPE_CHECKING:
    from codex.models import Comic

# Two questions on one comic, one per source, as a merge run can leave.
_METRON_FP: Final = "fp-metron"
_COMICVINE_FP: Final = "fp-comicvine"


def _metron_prompt(comics: list[dict[str, Any]]) -> dict[str, Any]:
    """Metron's question on the same comics, its candidate naming the volume."""
    candidates = [{"issue_id": METRON_ID, "source": "metron", "volume_id": VOLUME_ID}]
    return make_prompt(
        comics, fingerprint=_METRON_FP, source="metron", candidates=candidates
    )


def _comicvine_prompt(
    comics: list[dict[str, Any]], candidates: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Comic Vine's question on the same comics."""
    return make_prompt(comics, fingerprint=_COMICVINE_FP, candidates=candidates)


def _landed(comic: Comic, source: str, issue_id: int) -> SimpleNamespace:
    """Build a replay that landed the pick on ``source``'s ``issue_id``."""
    return SimpleNamespace(
        path=Path(comic.path),
        tags=answer(source, issue_id),
        error=None,
        matched=True,
    )


class BackToBackAnswerTests(OnlineTagSessionTestCase):
    """
    Two sources ask about one comic and the admin answers both in a row.

    Neither answer finds the other in the database: the first one's write
    is only queued when the second is applied, and the scan saw neither
    source write. Once the first write is queued, its issue id is noted on
    the comic in the other prompt, so the second merges under it when the
    first ranks higher.
    """

    @override
    def setUp(self) -> None:
        super().setUp()
        ComicboxTaggingDefaults.objects.filter(pk=1).update(comicvine_key="k")

    def _patches_for(self, comic: Comic) -> list[dict[str, Any]]:
        """Return the tags each queued write gives ``comic``, in queue order."""
        return [
            task.per_comic_patches[comic.pk]
            for task in self.write_tasks()
            if comic.pk in task.comic_pks
        ]

    def _seed(self, *comics: Comic, comicvine_candidates=None) -> None:
        """Cache both questions, with nothing noted on their comics."""
        for comic in comics:
            write_archive(comic, "old title")
        entries = [comic_entry(comic) for comic in comics]
        set_pending_prompts(
            {
                _METRON_FP: _metron_prompt(entries),
                _COMICVINE_FP: _comicvine_prompt(
                    [dict(entry) for entry in entries], comicvine_candidates
                ),
            }
        )

    def test_the_lower_pick_answered_next_keeps_the_higher_ones_title(self) -> None:
        comic = make_comic()
        self._seed(comic)

        with fake_sources() as sources:
            self.manager.resolve_prompt(_METRON_FP, "choose", 0, None)
            self.manager.resolve_prompt(_COMICVINE_FP, "choose", 0, None)

        metron_tags, comicvine_tags = self._patches_for(comic)
        assert metron_tags["title"] == "title from metron"
        assert comicvine_tags["title"] == "title from metron"
        assert comicvine_tags["identifiers"]["comicvine"]["key"] == str(COMICVINE_ID)
        assert sources["metron"].get_calls == [METRON_ID, METRON_ID]

    def test_the_queued_write_is_noted_on_the_other_prompt(self) -> None:
        """The review dialog is told, so it says Metron already tagged it."""
        comic = make_comic()
        self._seed(comic)

        with fake_sources():
            self.manager.resolve_prompt(_METRON_FP, "choose", 0, None)

        (entry,) = get_pending_prompts()[_COMICVINE_FP]["comics"]
        assert entry["tagged_ids"] == {"metron": METRON_ID}
        assert entry["tagged_by"] == ["metron"]
        assert self.queue.items[-1] is ONLINE_TAG_PROMPT_TASK

    def test_the_higher_pick_answered_second_wins(self) -> None:
        """Metron's patch is queued last and fetches nothing ranked below it."""
        comic = make_comic()
        self._seed(comic)

        with fake_sources() as sources:
            self.manager.resolve_prompt(_COMICVINE_FP, "choose", 0, None)
            self.manager.resolve_prompt(_METRON_FP, "choose", 0, None)

        comicvine_tags, metron_tags = self._patches_for(comic)
        assert comicvine_tags["title"] == "title from comicvine"
        assert metron_tags["title"] == "title from metron"
        assert sources["comicvine"].get_calls == [COMICVINE_ID]

    def test_a_failed_pick_notes_nothing(self) -> None:
        comic = make_comic()
        self._seed(comic)

        with fake_sources() as sources:
            sources["metron"].failing.add(METRON_ID)
            self.manager.resolve_prompt(_METRON_FP, "choose", 0, None)
            (entry,) = get_pending_prompts()[_COMICVINE_FP]["comics"]
            self.manager.resolve_prompt(_COMICVINE_FP, "choose", 0, None)

        assert entry["tagged_ids"] == {}
        assert entry["tagged_by"] == []
        (comicvine_tags,) = self._patches_for(comic)
        assert comicvine_tags["title"] == "title from comicvine"
        assert sources["metron"].get_calls == [METRON_ID]

    def test_each_follower_is_noted_with_its_own_issue(self) -> None:
        representative, follower = make_series_comics(2)
        follower_metron_id = METRON_ID + 1
        self._seed(representative, follower)
        FakeSession.tag_results = [_landed(follower, "metron", follower_metron_id)]

        with fake_sources() as sources, patch(APPLY_SESSION_TARGET, FakeSession):
            self.manager.resolve_prompt(_METRON_FP, "choose", 0, VOLUME_ID)
            noted = {
                entry["pk"]: entry["tagged_ids"]
                for entry in get_pending_prompts()[_COMICVINE_FP]["comics"]
            }
            FakeSession.tag_results = [replayed(follower)]
            self.manager.resolve_prompt(_COMICVINE_FP, "choose", 0, VOLUME_ID)

        assert noted == {
            representative.pk: {"metron": METRON_ID},
            follower.pk: {"metron": follower_metron_id},
        }
        for comic in (representative, follower):
            assert self._patches_for(comic)[-1]["title"] == "title from metron"
        assert sources["metron"].get_calls == [
            METRON_ID,
            METRON_ID,
            follower_metron_id,
        ]

    def test_the_note_survives_a_drifted_re_ask(self) -> None:
        comic = make_comic()
        self._seed(
            comic, comicvine_candidates=[{"source": "comicvine", "volume_id": 9}]
        )
        FakeSession.tag_results = [
            SimpleNamespace(path=Path(comic.path), tags={}, error=None, matched=False)
        ]
        FakeSession.deferred = [FakeDP(Path(comic.path), "fp-fresh", "comicvine")]

        with fake_sources(), patch(APPLY_SESSION_TARGET, FakeSession):
            self.manager.resolve_prompt(_METRON_FP, "choose", 0, None)
            self.manager.resolve_prompt(_COMICVINE_FP, "choose", 0, 9)
            (entry,) = get_pending_prompts()["fp-fresh"]["comics"]
            self.manager.resolve_prompt("fp-fresh", "choose", 0, None)

        assert entry["tagged_ids"] == {"metron": METRON_ID}
        assert entry["tagged_by"] == ["metron"]
        assert self._patches_for(comic)[-1]["title"] == "title from metron"

    def test_answers_held_until_the_scan_ends_merge_in_order(self) -> None:
        """
        Answers given mid-scan leave the cache at once and apply afterwards.

        So the note has nowhere to land in the cache: the held answers
        carry it from one to the next instead.
        """
        comic = make_comic()
        self._seed(comic)
        prompts = get_pending_prompts()
        set_pending_prompts({})
        state = SessionState(session=double(FakeSession()))
        state.deferred_applies.extend(
            (prompts[fingerprint], "choose", 0, None)
            for fingerprint in (_METRON_FP, _COMICVINE_FP)
        )

        with fake_sources():
            self.manager._apply_deferred_resolutions(state)  # noqa: SLF001

        metron_tags, comicvine_tags = self._patches_for(comic)
        assert metron_tags["title"] == "title from metron"
        assert comicvine_tags["title"] == "title from metron"


class NoteTaggedIdsTests(SimpleTestCase):
    """How a queued write's issue id lands on another prompt's comics."""

    @staticmethod
    def _bare_prompt(source: str = "comicvine", **comic: Any) -> dict[str, Any]:
        return {"source": source, "comics": [{"pk": 1, "path": "/c1.cbz", **comic}]}

    def test_only_the_written_comic_is_noted(self) -> None:
        prompt = self._bare_prompt()
        prompt["comics"].append({"pk": 2, "path": "/c2.cbz"})

        assert note_tagged_ids(prompt, {1: {"metron": METRON_ID}})
        assert prompt["comics"] == [
            {
                "pk": 1,
                "path": "/c1.cbz",
                "tagged_by": ["metron"],
                "tagged_ids": {"metron": METRON_ID},
            },
            {"pk": 2, "path": "/c2.cbz"},
        ]

    def test_a_prompt_is_never_noted_with_its_own_source(self) -> None:
        prompt = self._bare_prompt(source="metron")

        assert not note_tagged_ids(prompt, {1: {"metron": METRON_ID}})
        assert "tagged_ids" not in prompt["comics"][0]

    def test_what_is_already_known_changes_nothing(self) -> None:
        prompt = self._bare_prompt(
            tagged_by=["metron"], tagged_ids={"metron": METRON_ID}
        )

        assert not note_tagged_ids(prompt, {1: {"metron": METRON_ID}})

    def test_a_newer_id_replaces_the_one_noted(self) -> None:
        prompt = self._bare_prompt(
            tagged_by=["metron"], tagged_ids={"metron": METRON_ID}
        )

        assert note_tagged_ids(prompt, {1: {"metron": METRON_ID + 1}})
        (comic,) = prompt["comics"]
        assert comic["tagged_ids"] == {"metron": METRON_ID + 1}
        assert comic["tagged_by"] == ["metron"]

    def test_a_prompt_cached_before_the_comic_list_gains_one(self) -> None:
        prompt: dict[str, Any] = {"source": "comicvine", "pk": 1, "path": "/c1.cbz"}

        assert note_tagged_ids(prompt, {1: {"metron": METRON_ID}})
        assert prompt["comics"][0]["tagged_ids"] == {"metron": METRON_ID}
