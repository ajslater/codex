"""
B20: under Merge all sources a comic's stored ids are fetched, the rest searched.

A comic Codex held a stored issue id for was fetched by that id and taken out
of the run, so a selected source it had no id for was never asked: on an
already-tagged library, adding a VerseDB key and re-running with Merge all
sources fetched Metron by id and never asked VerseDB.

Now each selected source the comic has a stored id for is fetched by it, and
each one it has none for is searched, in one lookup of that comic alone, so
comicbox merges them in the admin's source order and the comic's ids reach no
other comic. A comic with ids for every source is still fetched by id alone,
one with none is searched with the rest of the run, and First match is
unchanged.

A lookup of its own, rather than leaving the comic in the run, because a plain
session cannot see an id that only ComicInfo holds: ``StoredIdSightTests``.
"""

from __future__ import annotations

import queue
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Final, override
from unittest.mock import patch

import pytest
from comicbox.box import Comicbox
from comicbox.events import AutoWritten, FileFinished, PromptDeferred, SourceStarted
from comicbox.formats.base.online.profile import Candidate, CandidateSummary
from comicbox.formats.comicbox.schema import IDENTIFIERS_KEY
from comicbox.identifiers import ID_KEY_KEY
from comicbox.write import BulkWriteItem, bulk_write

from codex.librarian.onlinetag.session_cache import get_pending_prompts
from codex.librarian.onlinetag.session_snapshot import get_resume_state, get_snapshot
from codex.librarian.onlinetag.session_state import SessionState
from codex.librarian.onlinetag.statuses import QUEUED
from codex.librarian.onlinetag.tasks import (
    BulkOnlineTagTask,
    OnlineTagPromptResponseTask,
)
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import ComicboxTaggingDefaults, Identifier, IdentifierSource
from codex.models.identifier import IdentifierType
from tests.onlinetag_merge_fakes import (
    COMICVINE_ID,
    METRON_ID,
    ORDER,
    VOLUME_ID,
    answer,
    fake_sources,
    write_archive,
)
from tests.onlinetag_session_fakes import (
    FETCH_TARGET,
    PATCH_TARGET,
    FakeDP,
    FakeSession,
    OnlineTagSessionTestCase,
    double,
    make_comic,
    make_series_comics,
)

if TYPE_CHECKING:
    from codex.models import Comic

_SESSION_ID: Final = "s"
_SERIES_KEY: Final = ("comicvine", "series S")
_VERSEDB_ID: Final = 77


class _Session(FakeSession):
    """The scan's fake sessions, with the rate budget the snapshot reads."""

    def rate_limit_status(self) -> dict[str, dict]:
        return {}


def _store_issue_id(comic: Comic, source_name: str, issue_id: int) -> None:
    """Give the comic a stored issue id, as an earlier tag's re-import does."""
    source, _ = IdentifierSource.objects.get_or_create(name=source_name)
    identifier = Identifier.objects.create(
        source=source, id_type=IdentifierType.ISSUE.value, key=str(issue_id)
    )
    comic.identifiers.add(identifier)


def _task(comics: list[Comic], **kwargs: Any) -> BulkOnlineTagTask:
    """Build a Merge all sources run over ``comics``, Metron then Comic Vine."""
    params: dict[str, Any] = {"sources": ORDER, "merge_all_sources": True}
    params.update(kwargs)
    return BulkOnlineTagTask(
        comic_pks=frozenset(comic.pk for comic in comics),
        session_id=_SESSION_ID,
        **params,
    )


class MergeAllPrepassTests(OnlineTagSessionTestCase):
    """Every selected source is asked, as the Tagging tab says."""

    @override
    def setUp(self) -> None:
        super().setUp()
        ComicboxTaggingDefaults.objects.filter(pk=1).update(comicvine_key="k")
        self.fetches: list[dict[str, Any]] = []  # pyright: ignore[reportUninitializedInstanceVariable]

    def _fetch(self, path, source, issue_id, _credentials, **kwargs) -> dict:
        """Record an id-only fetch and land every id it asked for."""
        extra_ids = kwargs.get("extra_ids", ())
        self.fetches.append(
            {"path": path, "source": source, "id": issue_id, "extra_ids": extra_ids}
        )
        ids = {source: issue_id, **dict(extra_ids)}
        return {
            "series": "X",
            IDENTIFIERS_KEY: {s: {ID_KEY_KEY: str(i)} for s, i in ids.items()},
        }

    def _run(self, task: BulkOnlineTagTask, session_class: type = _Session) -> None:
        with patch(PATCH_TARGET, session_class), patch(FETCH_TARGET, self._fetch):
            self.manager.run_session(task)

    @staticmethod
    def _main() -> FakeSession:
        """Return the run's own session, built before any comic's."""
        return FakeSession.instances[0]

    @staticmethod
    def _comic_sessions() -> list[FakeSession]:
        """Return the one-comic sessions, in the order they were built."""
        return FakeSession.instances[1:]

    def _written(self) -> dict[int, dict]:
        """Every comic the run queued a write for, with its tags."""
        return {
            pk: tags
            for task in self.write_tasks()
            for pk, tags in task.per_comic_patches.items()
        }

    def test_a_source_without_a_stored_id_is_still_asked(self) -> None:
        """The comic is looked up with Metron pinned, so VerseDB searches."""
        ComicboxTaggingDefaults.objects.filter(pk=1).update(versedb_key="v")
        comic = make_comic()
        source, _ = IdentifierSource.objects.get_or_create(name="metron")
        comic.identifiers.add(
            Identifier.objects.create(source=source, id_type="comic", key="123495")
        )
        path = Path(comic.path)
        comic_paths = {comic.pk: path}
        state = SessionState(
            session=double(FakeSession()),
            path_to_pk={path: comic.pk},
            sources=("metron", "versedb"),
        )
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="s",
            sources=("metron", "versedb"),
            merge_all_sources=True,
        )
        credentials = self.manager._build_credentials()  # noqa: SLF001
        assert credentials is not None

        with patch(FETCH_TARGET, self._fetch):
            pinned = self.manager._prefetch_stored_ids(  # noqa: SLF001
                state, comic_paths, task, credentials
            )

        # Not fetched by id alone: handed to a lookup of its own, which pins
        # Metron's id and leaves VerseDB to search.
        assert self.fetches == []
        assert pinned == {path: {"metron": 123495}}
        assert comic_paths == {}

    def test_ids_for_every_source_fetch_by_id_alone(self) -> None:
        comic = make_comic()
        _store_issue_id(comic, "metron", METRON_ID)
        _store_issue_id(comic, "comicvine", COMICVINE_ID)

        self._run(_task([comic]))

        assert self.fetches == [
            {
                "path": Path(comic.path),
                "source": "metron",
                "id": METRON_ID,
                "extra_ids": (("comicvine", COMICVINE_ID),),
            }
        ]
        assert self._comic_sessions() == []
        assert self._main().tagged == []
        assert comic.pk in self._written()

    def test_ids_for_some_search_exactly_the_others(self) -> None:
        """Comic Vine's id is pinned; Metron, which has none, searches."""
        comic = make_comic()
        _store_issue_id(comic, "comicvine", COMICVINE_ID)

        self._run(_task([comic]))

        (lookup,) = self._comic_sessions()
        # Pinned: only the id the comic has. Searched: every other selected
        # source. Merged: every source runs, the admin's first winning.
        assert lookup.kwargs["ids"] == {"comicvine": COMICVINE_ID}
        assert lookup.kwargs["sources"] == ORDER
        assert lookup.kwargs["first_wins"] is False
        assert lookup.tagged == [Path(comic.path)]
        assert self._main().tagged == []
        assert self.fetches == []
        assert self._written() == {comic.pk: {"series": "X"}}

    def test_no_ids_take_the_normal_search_pass(self) -> None:
        comic = make_comic()

        self._run(_task([comic]))

        assert self.fetches == []
        assert self._comic_sessions() == []
        assert self._main().tagged == [Path(comic.path)]
        assert self._main().kwargs["ids"] == {}

    def test_first_match_is_unchanged(self) -> None:
        """A first-match run fetches the stored id and asks no one else."""
        comic = make_comic()
        _store_issue_id(comic, "comicvine", COMICVINE_ID)

        self._run(_task([comic], merge_all_sources=False))

        assert self.fetches == [
            {
                "path": Path(comic.path),
                "source": "comicvine",
                "id": COMICVINE_ID,
                "extra_ids": (),
            }
        ]
        assert self._comic_sessions() == []
        assert self._main().tagged == []

    def test_each_comic_is_looked_up_with_its_own_ids(self) -> None:
        """One comic's ids never reach another's lookup."""
        first, second = make_series_comics(2)
        _store_issue_id(first, "comicvine", COMICVINE_ID)
        _store_issue_id(second, "comicvine", COMICVINE_ID + 1)

        self._run(_task([first, second]))

        by_path = {
            tuple(lookup.tagged): lookup.kwargs["ids"]
            for lookup in self._comic_sessions()
        }
        assert by_path == {
            (Path(first.path),): {"comicvine": COMICVINE_ID},
            (Path(second.path),): {"comicvine": COMICVINE_ID + 1},
        }

    def test_a_comic_arriving_mid_scan_joins_no_pinned_lookup(self) -> None:
        """A merged task's comic goes to the run's own unpinned session."""
        comic = make_comic(name="pinned")
        _store_issue_id(comic, "comicvine", COMICVINE_ID)
        late = make_comic(name="late")
        thread_queue: queue.Queue = queue.Queue()
        thread_queue.put(_task([late]))
        self.manager.thread_queue = thread_queue

        self._run(_task([comic]))

        (lookup,) = self._comic_sessions()
        assert lookup.tagged == [Path(comic.path)]
        assert self._main().tagged == [Path(late.path)]
        assert self._main().kwargs["ids"] == {}

    def test_status_and_snapshot_count_each_comic_once(self) -> None:
        """A comic of each kind: all ids, some, none."""
        comics = make_series_comics(3)
        every, some, none = comics
        _store_issue_id(every, "metron", METRON_ID)
        _store_issue_id(every, "comicvine", COMICVINE_ID)
        _store_issue_id(some, "comicvine", COMICVINE_ID + 1)
        FakeSession.tag_results = [
            SimpleNamespace(
                path=Path(none.path),
                tags={"series": "X"},
                matched=True,
                error=None,
                cancelled=False,
            )
        ]

        self._run(_task([every, some, none]))

        snapshot = get_snapshot()
        assert snapshot is not None
        batch = snapshot["batch"]
        assert batch["total"] == batch["completed"] == len(comics)
        assert set(self._written()) == {every.pk, some.pk, none.pk}

    def test_a_series_resolved_for_one_comic_is_reused_by_the_next(self) -> None:
        """The run searches a series once, not once per comic."""
        first, second, third = make_series_comics(3)
        for comic in (first, second):
            _store_issue_id(comic, "comicvine", COMICVINE_ID + comic.pk)

        class _Resolving(_Session):
            seeded: dict[tuple[str, str], int] | None = None

            @override
            def tag(self, path):
                # What this lookup was seeded with, before it looks anything up.
                self.seeded = dict(self.series_cache)
                # The first lookup resolves the series; later ones are seeded.
                if not self.series_cache:
                    self.series_cache[_SERIES_KEY] = VOLUME_ID
                return super().tag(path)

        self._run(_task([first, second, third]), session_class=_Resolving)

        lookups = self._comic_sessions()
        assert [getattr(lookup, "seeded", None) for lookup in lookups] == [
            {},
            {_SERIES_KEY: VOLUME_ID},
        ]
        # The search pass's comic gets it too.
        assert self._main().series_cache == {_SERIES_KEY: VOLUME_ID}

    def test_a_mid_scan_answer_reaches_later_comic_lookups(self) -> None:
        """A pick naming a volume is preloaded into every later lookup."""
        comic = make_comic()
        path = Path(comic.path)
        state = SessionState(session=double(_Session()), path_to_pk={path: 1})
        item = OnlineTagPromptResponseTask(
            prompt_fingerprint="fp1",
            action="choose",
            payload=0,
            chosen_volume_id=VOLUME_ID,
        )
        task = _task([comic])
        credentials = self.manager._build_credentials()  # noqa: SLF001
        assert credentials is not None

        self.manager._preload_mid_scan_answer(state, item)  # noqa: SLF001
        with patch(PATCH_TARGET, _Session):
            self.manager._comic_session(  # noqa: SLF001
                state, task, credentials, {"comicvine": COMICVINE_ID}
            )

        assert FakeSession.preloaded == [("fp1", "choose", 0, VOLUME_ID)] * 2

    def test_a_pause_stops_before_the_next_comic(self) -> None:
        """
        The lookup under way is written; the next comic is left for Resume.

        The Pause arrives from another thread mid-lookup. comicbox's
        ``cancel()`` only sets an event, so that lookup runs to its end and
        comes back matched.
        """
        first, second = make_series_comics(2)
        _store_issue_id(first, "comicvine", COMICVINE_ID)
        _store_issue_id(second, "comicvine", COMICVINE_ID + 1)
        manager = self.manager

        class _Paused(_Session):
            @override
            def tag_one(self, path):
                manager.cancel_session(_SESSION_ID)
                return super().tag_one(path)

        self._run(_task([first, second]), session_class=_Paused)

        (lookup,) = self._comic_sessions()
        assert lookup.cancelled
        (looked_up,) = lookup.tagged
        pk_by_path = {Path(comic.path): comic.pk for comic in (first, second)}
        assert set(self._written()) == {pk_by_path[looked_up]}
        resume = get_resume_state()
        assert resume is not None
        assert set(resume["remaining_pks"]) == (
            set(pk_by_path.values()) - {pk_by_path[looked_up]}
        )

    def test_a_raise_mid_pass_still_writes_what_matched(self) -> None:
        """A session that cannot be built loses no comic already matched."""
        first, second = make_series_comics(2)
        _store_issue_id(first, "comicvine", COMICVINE_ID)
        _store_issue_id(second, "comicvine", COMICVINE_ID + 1)
        reason = "no session"

        class _SecondFails(_Session):
            def __init__(self, **kwargs) -> None:
                # The run's own session, then one lookup, then this raise.
                if len(FakeSession.instances) == len((first, second)):
                    raise RuntimeError(reason)
                super().__init__(**kwargs)

        with pytest.raises(RuntimeError, match=reason):
            self._run(_task([first, second]), session_class=_SecondFails)

        (lookup,) = self._comic_sessions()
        (looked_up,) = lookup.tagged
        pk_by_path = {Path(comic.path): comic.pk for comic in (first, second)}
        assert set(self._written()) == {pk_by_path[looked_up]}
        resume = get_resume_state()
        assert resume is not None
        assert set(resume["remaining_pks"]) == (
            set(pk_by_path.values()) - {pk_by_path[looked_up]}
        )

    def test_the_searched_halfs_prompt_keeps_the_run_order(self) -> None:
        """
        Metron is pinned and writes; Comic Vine's search asks.

        The prompt carries the run's order and the id Metron wrote, so the
        answer, given after the scan, is merged under Metron's issue instead
        of overwriting it.
        """
        comic = make_comic()
        _store_issue_id(comic, "metron", METRON_ID)

        class _Asking(_Session):
            asked: tuple[FakeDP, ...] = ()

            @override
            def deferred_prompts(self):
                return list(self.asked)

            @override
            def tag_one(self, path):
                on_event = self.kwargs["on_event"]
                for event in (
                    SourceStarted(path=path, source="metron"),
                    AutoWritten(
                        path=path, source="metron", candidate_summary=str(METRON_ID)
                    ),
                    SourceStarted(path=path, source="comicvine"),
                ):
                    on_event(event)
                self.asked = (FakeDP(path, "fp1", "comicvine"),)
                on_event(
                    PromptDeferred(path=path, source="comicvine", fingerprint="fp1")
                )
                on_event(FileFinished(path=path, outcome="written"))
                return super().tag_one(path)

        self._run(_task([comic]), session_class=_Asking)

        prompt = get_pending_prompts()["fp1"]
        assert prompt["source_order"] == list(ORDER)
        assert prompt["merge_all_sources"] is True
        assert prompt["comics"][0]["pk"] == comic.pk
        assert prompt["comics"][0]["tagged_ids"] == {"metron": METRON_ID}

        write_archive(comic, "title from metron")
        self.queue.items.clear()
        with fake_sources() as sources:
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        (tags,) = self._written().values()
        assert tags["title"] == answer("metron", METRON_ID)["title"]
        assert tags["identifiers"]["comicvine"]["key"] == str(COMICVINE_ID)
        assert sources["metron"].get_calls == [METRON_ID]
        assert sources["comicvine"].get_calls == [COMICVINE_ID]


def _candidate(source: str, issue_id: int) -> Candidate:
    """Rank the one issue the comic is, as ``source`` would."""
    summary = CandidateSummary(
        series="S",
        issue="1",
        year=None,
        publisher=None,
        page_count=None,
        cover_url=None,
        variant_label=None,
    )
    return Candidate(
        source=source,
        issue_id=issue_id,
        summary=summary,
        metadata_score=1.0,
        score=1.0,
        volume_id=VOLUME_ID,
    )


def _matching_search(source) -> Any:
    """Search as a source does, answering with the one issue the comic is."""
    issue_ids = {"comicvine": COMICVINE_ID, "versedb": _VERSEDB_ID}

    def search(_profile) -> list[Candidate]:
        source.search_calls += 1
        return [_candidate(source.name, issue_ids[source.name])]

    return search


def _failing_search(source) -> Any:
    """Comic Vine's search, refused as a revoked key or a spent retry is."""

    def search(_profile) -> list[Candidate]:
        source.search_calls += 1
        reason = "401 Unauthorized"
        raise ConnectionError(reason)

    return search


class MixedLookupMergeTests(OnlineTagSessionTestCase):
    """comicbox's real merge, with fake sources standing in for the APIs."""

    @override
    def setUp(self) -> None:
        super().setUp()
        ComicboxTaggingDefaults.objects.filter(pk=1).update(comicvine_key="k")
        self.comic = make_comic()  # pyright: ignore[reportUninitializedInstanceVariable]
        write_archive(self.comic, "old")
        _store_issue_id(self.comic, "metron", METRON_ID)

    def _look_up(self, sources: dict[str, Any], search) -> dict[str, Any] | None:
        """Run the scan with Comic Vine searching as ``search`` does."""
        comicvine = sources["comicvine"]
        comicvine.search = search(comicvine)
        # The series a cold search resolves is offered for listing whole.
        comicvine.prefetch_volume = lambda *_args: None
        self.manager.run_session(_task([self.comic]))
        writes = [t for t in self.queue.items if isinstance(t, BulkTagWriteTask)]
        return writes[0].per_comic_patches[self.comic.pk] if writes else None

    def test_the_pinned_and_searched_halves_merge_in_source_order(self) -> None:
        """Metron is pinned and first, so its title wins; both ids land."""
        with fake_sources() as sources:
            tags = self._look_up(sources, _matching_search)

        assert tags is not None
        assert tags["title"] == answer("metron", METRON_ID)["title"]
        assert tags["identifiers"]["metron"]["key"] == str(METRON_ID)
        assert tags["identifiers"]["comicvine"]["key"] == str(COMICVINE_ID)
        assert set(tags["genres"]) == {"metron", "comicvine"}
        assert sources["metron"].get_calls == [METRON_ID]
        assert sources["metron"].search_calls == 0
        assert sources["comicvine"].search_calls == 1
        assert sources["comicvine"].get_calls == [COMICVINE_ID]

    def test_a_failing_search_keeps_the_by_id_half(self) -> None:
        """Comicbox fails the one source, not the comic: Metron still lands."""
        with fake_sources() as sources:
            tags = self._look_up(sources, _failing_search)

        assert tags is not None
        assert tags["title"] == answer("metron", METRON_ID)["title"]
        assert "comicvine" not in tags["identifiers"]
        assert sources["comicvine"].search_calls == 1

    def test_a_stored_id_that_fails_holds_the_comic_for_resume(self) -> None:
        """
        Not written, not searched, and queued for Resume.

        Writing Comic Vine's half would put a lower-priority source's title
        over the Metron one the comic had, and mark the comic done.
        """
        with fake_sources() as sources:
            sources["metron"].failing.add(METRON_ID)
            tags = self._look_up(sources, _matching_search)

        assert tags is None
        assert sources["metron"].get_calls == [METRON_ID]
        assert sources["metron"].search_calls == 0
        resume = get_resume_state()
        assert resume is not None
        assert resume["remaining_pks"] == [self.comic.pk]
        snapshot = get_snapshot()
        assert snapshot is not None
        (row,) = snapshot["comics"]
        assert row["status"] == QUEUED


class StoredIdSightTests(OnlineTagSessionTestCase):
    """
    What a plain session does with the ids a comic's file holds.

    comicbox refreshes a source by id when the comic's own metadata holds
    that source's issue id, but it reads ids one tag format at a time.
    MetronInfo stores them as ids. ComicInfo stores them as links and notes,
    which comicbox turns into ids only in its merged record, and that record
    is what codex's importer stores. So when a comic's ids are only in
    ComicInfo, the database holds ids a plain session never sees, and only a
    lookup that pins them uses them.

    If the second test fails, comicbox reads those ids now, and a partly
    identified comic could simply stay in the run's own session.
    """

    @override
    def setUp(self) -> None:
        super().setUp()
        ComicboxTaggingDefaults.objects.filter(pk=1).update(versedb_key="v")
        self.comic = make_comic()  # pyright: ignore[reportUninitializedInstanceVariable]
        write_archive(self.comic, "old")

    def _write_metron_id(self, fmt: str) -> None:
        """Write Metron's id into the comic, as codex's tag write does."""
        item = BulkWriteItem(
            path=Path(self.comic.path),
            patch={"identifiers": {"metron": {ID_KEY_KEY: str(METRON_ID)}}},
            merge_mode="update",
            formats=frozenset({fmt}),
        )
        list(bulk_write([item]))
        # The importer stores the merged record, which holds the id either way.
        with Comicbox(Path(self.comic.path)) as cb:
            merged = cb.to_dict()["comicbox"][IDENTIFIERS_KEY]
        assert merged["metron"][ID_KEY_KEY] == str(METRON_ID)

    def _scan(self, sources: dict[str, Any]) -> None:
        """Tag the comic with Metron then VerseDB, no stored id in the database."""
        versedb = sources["versedb"]
        versedb.search = _matching_search(versedb)
        versedb.prefetch_volume = lambda *_args: None
        self.manager.run_session(_task([self.comic], sources=("metron", "versedb")))

    def test_a_metroninfo_id_is_fetched_by_a_plain_session(self) -> None:
        """One Metron fetch by id, a VerseDB search, merged in source order."""
        self._write_metron_id("METRON_INFO")

        with fake_sources() as sources:
            self._scan(sources)

        assert sources["metron"].get_calls == [METRON_ID]
        assert sources["metron"].search_calls == 0
        assert sources["versedb"].search_calls == 1
        (write,) = (t for t in self.queue.items if isinstance(t, BulkTagWriteTask))
        tags = write.per_comic_patches[self.comic.pk]
        assert tags["title"] == answer("metron", METRON_ID)["title"]
        assert tags[IDENTIFIERS_KEY]["versedb"][ID_KEY_KEY] == str(_VERSEDB_ID)

    def test_a_comicinfo_only_id_is_not_seen_by_a_plain_session(self) -> None:
        """The same id, written only to ComicInfo, sends Metron to search."""
        self._write_metron_id("COMIC_INFO")

        with fake_sources() as sources:
            self._scan(sources)

        assert sources["metron"].get_calls == []
        assert sources["metron"].search_calls == 1
