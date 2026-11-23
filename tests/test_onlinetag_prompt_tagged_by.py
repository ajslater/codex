"""
A pending prompt names the sources that tagged its comic anyway.

With several sources and first-wins, one source (Metron, which defers cover
matches) can leave a prompt for a comic that a later source (Comic Vine)
then writes in the same scan. The comic still reads "Needs review", since the
two sources' data don't overlap perfectly, but its prompt carries the sources
that wrote it so the review dialog can say so. Each comic of a series-level
prompt carries its own list, and a prompt cached before the list existed is
served as it was.
"""

from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from typing import Final
from unittest.mock import patch

from comicbox.events import AutoWritten, FileFinished, PromptDeferred, SourceStarted
from django.contrib.auth.models import User
from django.test import Client

from codex.librarian.onlinetag.session_cache import (
    get_pending_prompts,
    set_pending_prompts,
)
from codex.librarian.onlinetag.tasks import BulkOnlineTagTask
from tests.onlinetag_session_fakes import (
    APPLY_SESSION_TARGET,
    PATCH_TARGET,
    FakeDP,
    FakePassRunner,
    FakeSession,
    OnlineTagSessionTestCase,
    double,
    make_comic,
    make_series_comics,
)

_TEST_PASSWORD: Final = "test-pw-hush-T448"  # noqa: S105
_PROMPTS_URL: Final = "/api/v4/admin/tag-prompts"
_SOURCES: Final = ("metron", "comicvine")


def _deferred(path: Path, fingerprint: str = "fp1") -> list:
    """Emit Metron deferring a prompt for ``path``, as comicbox does."""
    return [
        SourceStarted(path=path, source="metron"),
        PromptDeferred(path=path, source="metron", fingerprint=fingerprint),
    ]


def _written(path: Path) -> list:
    """Emit Comic Vine writing ``path`` after Metron's turn."""
    return [
        SourceStarted(path=path, source="comicvine"),
        AutoWritten(path=path, source="comicvine"),
    ]


def _finished(path: Path, outcome: str) -> list:
    return [FileFinished(path=path, outcome=outcome)]


class PromptTaggedByScanTests(OnlineTagSessionTestCase):
    """The scan records, on each prompt's comic, who wrote it."""

    def _run(self, comics, drive) -> None:
        """Run a Metron-then-Comic Vine scan whose pass body is ``drive``."""
        self.manager._pass_runner = double(FakePassRunner(drive))  # noqa: SLF001
        task = BulkOnlineTagTask(
            comic_pks=frozenset(comic.pk for comic in comics),
            session_id="scan-tagged-by",
            sources=_SOURCES,
            mode="auto",
        )
        with patch(PATCH_TARGET, FakeSession):
            self.manager.run_session(task)

    def test_a_later_source_that_writes_the_comic_is_named(self) -> None:
        comic = make_comic()
        path = Path(comic.path)
        FakeSession.deferred = [FakeDP(path, "fp1", "metron")]
        on_event = self.manager._on_event  # noqa: SLF001
        mid_scan: list = []

        def _drive(_state, _paths, **_kwargs) -> None:
            for event in _deferred(path) + _written(path):
                on_event(event)
            # Cached as soon as it is known, not only when the scan ends.
            mid_scan.append(get_pending_prompts()["fp1"]["comics"][0])
            for event in _finished(path, "written"):
                on_event(event)

        self._run([comic], _drive)

        assert mid_scan[0]["tagged_by"] == ["comicvine"]
        prompt = get_pending_prompts()["fp1"]
        assert prompt["source"] == "metron"
        # This AutoWritten names no issue id, so none is recorded.
        assert prompt["comics"] == [
            {
                "pk": comic.pk,
                "path": str(path),
                "tagged_by": ["comicvine"],
                "tagged_ids": {},
            }
        ]

    def test_a_comic_no_other_source_wrote_names_none(self) -> None:
        comic = make_comic()
        path = Path(comic.path)
        FakeSession.deferred = [FakeDP(path, "fp1", "metron")]
        on_event = self.manager._on_event  # noqa: SLF001

        def _drive(_state, _paths, **_kwargs) -> None:
            for event in _deferred(path) + _finished(path, "no_change"):
                on_event(event)

        self._run([comic], _drive)

        assert get_pending_prompts()["fp1"]["comics"][0]["tagged_by"] == []

    def test_each_comic_of_a_series_prompt_has_its_own(self) -> None:
        first, second = make_series_comics(2)
        first_path, second_path = Path(first.path), Path(second.path)
        FakeSession.deferred = [
            FakeDP(first_path, "fp1", "metron"),
            FakeDP(second_path, "fp1", "metron"),
        ]
        on_event = self.manager._on_event  # noqa: SLF001

        def _drive(_state, _paths, **_kwargs) -> None:
            events = (
                _deferred(first_path)
                + _finished(first_path, "no_change")
                + _deferred(second_path)
                + _written(second_path)
                + _finished(second_path, "written")
            )
            for event in events:
                on_event(event)

        self._run([first, second], _drive)

        comics = get_pending_prompts()["fp1"]["comics"]
        tagged_by = {comic["pk"]: comic["tagged_by"] for comic in comics}
        assert tagged_by == {first.pk: [], second.pk: ["comicvine"]}


class PromptTaggedByDriftTests(OnlineTagSessionTestCase):
    """An answer whose replay drifts re-queues the comic with its note."""

    def test_a_drifted_requeue_keeps_the_note(self) -> None:
        comic = make_comic()
        path = Path(comic.path)
        set_pending_prompts(
            {
                "fp1": {
                    "fingerprint": "fp1",
                    "pk": comic.pk,
                    "path": str(path),
                    "comics": [
                        {"pk": comic.pk, "path": str(path), "tagged_by": ["comicvine"]}
                    ],
                    "source": "metron",
                    # No issue id: the answer replays the search, which drifts.
                    "candidates": [{"source": "metron"}],
                    "mode": "auto",
                    "formats": ["COMIC_INFO"],
                    "delete_original": False,
                }
            }
        )
        FakeSession.deferred = [FakeDP(path, "fp2", "metron")]
        FakeSession.tag_results = [
            SimpleNamespace(path=path, tags={}, error=None, matched=False)
        ]

        with patch(APPLY_SESSION_TARGET, FakeSession):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        prompts = get_pending_prompts()
        assert set(prompts) == {"fp2"}
        assert prompts["fp2"]["comics"][0]["tagged_by"] == ["comicvine"]


class PromptTaggedByEndpointTests(OnlineTagSessionTestCase):
    """The prompt list serves the note camelCased, and old prompts unchanged."""

    def test_the_prompt_list_serves_the_writing_sources(self) -> None:
        old = {"pk": 1, "path": "/c/1.cbz"}
        new = {"pk": 2, "path": "/c/2.cbz", "tagged_by": ["comicvine"]}
        set_pending_prompts(
            {
                fingerprint: {
                    "fingerprint": fingerprint,
                    "prompt_version": 2,
                    "pk": comic["pk"],
                    "path": comic["path"],
                    "comics": [comic],
                    "source": "metron",
                    "candidates": [],
                }
                for fingerprint, comic in (("fp-old", old), ("fp-new", new))
            }
        )
        admin = User.objects.create_user(
            username="tagged_by_admin", password=_TEST_PASSWORD, is_staff=True
        )
        client = Client()
        client.force_login(admin)

        response = client.get(_PROMPTS_URL)

        assert response.status_code == HTTPStatus.OK
        prompts = {p["fingerprint"]: p for p in response.json()["data"]["prompts"]}
        assert prompts["fp-new"]["comics"] == [
            {"pk": 2, "path": "/c/2.cbz", "taggedBy": ["comicvine"]}
        ]
        assert prompts["fp-old"]["comics"] == [{"pk": 1, "path": "/c/1.cbz"}]
