"""
An answered prompt keeps a Merge all sources run's merge order.

comicbox merges the sources one lookup queried with the first-listed source
winning every single-valued tag they disagree on, so the admin's source
order on the Tagging tab decides who wins a merge. A deferred prompt is
answered after its scan, though, and a pick applied on its own overwrote
what a higher-priority source had already written: in a Metron-then-Comic
Vine merge run, answering Comic Vine's question replaced Metron's title.

These tests run comicbox's real merge on a real archive, with fake online
sources standing in for the APIs, so nothing leaves the process.
"""

from __future__ import annotations

import zipfile
from contextlib import contextmanager
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import TYPE_CHECKING, Any, Final, override
from unittest.mock import patch

from comicbox.box.online_lookup import ONLINE_SOURCE_BY_NAME, ComicboxOnlineLookup
from comicbox.events import AutoWritten, FileFinished, PromptDeferred, SourceStarted
from comicbox.formats import MetadataFormats
from django.test import SimpleTestCase

from codex.librarian.onlinetag import explicit_id
from codex.librarian.onlinetag.outcome_stats import OnlineTagOutcomeStats
from codex.librarian.onlinetag.session_cache import (
    get_pending_prompts,
    set_pending_prompts,
)
from codex.librarian.onlinetag.tasks import BulkOnlineTagTask
from codex.models import (
    Comic,
    ComicboxTaggingDefaults,
    Identifier,
    IdentifierSource,
)
from codex.models.identifier import IdentifierType
from tests.onlinetag_session_fakes import (
    APPLY_FETCH_TARGET,
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

if TYPE_CHECKING:
    from collections.abc import Generator

    from comicbox.config.settings import ComicboxSettings

_ORDER: Final = ("metron", "comicvine")
_METRON_ID: Final = 101
# FakeDP's one candidate.
_COMICVINE_ID: Final = 123
# Where a replay lands: another Comic Vine issue of the picked volume.
_REPLAYED_ID: Final = 456
_VOLUME_ID: Final = 5


def _answer(name: str, issue_id: int) -> dict[str, Any]:
    """One source's answer: a single-valued tag, a keyed tag and its own id."""
    return {
        "title": f"title from {name}",
        "genres": {name: {}},
        "identifiers": {name: {"key": str(issue_id)}},
    }


class _FakeSource:
    """An online source that answers ``get`` from memory and records it."""

    def __init__(self, name: str) -> None:
        """Answer as ``name``, in comicbox's own schema."""
        self.name = name
        self.metadata_source = ONLINE_SOURCE_BY_NAME[name]
        self.metadata_format = MetadataFormats.COMICBOX_JSON
        self.get_calls: list[int] = []
        self.search_calls = 0

    def is_configured(self) -> bool:
        return True

    def get(self, issue_id: int) -> dict[str, Any]:
        self.get_calls.append(issue_id)
        return _answer(self.name, issue_id)

    def search(self, _profile) -> list:
        self.search_calls += 1
        return []


@contextmanager
def _fake_sources() -> Generator[dict[str, _FakeSource]]:
    """Have every comicbox lookup in the block build these sources."""
    sources = {name: _FakeSource(name) for name in ONLINE_SOURCE_BY_NAME}
    factories = MappingProxyType(
        {
            name: (lambda _creds, _settings, source=source: source)
            for name, source in sources.items()
        }
    )
    with patch.object(ComicboxOnlineLookup, "_ONLINE_SOURCE_FACTORIES", factories):
        yield sources


def _write_archive(comic: Comic, title: str) -> None:
    """Make the comic a real archive whose ComicInfo carries ``title``."""
    fields = f"<Series>S</Series><Number>1</Number><Title>{title}</Title>"
    with zipfile.ZipFile(comic.path, "w") as zf:
        zf.writestr("ComicInfo.xml", f"<ComicInfo>{fields}</ComicInfo>")


class _ScanSession(FakeSession):
    """The scan's fake session, with the rate budget the snapshot reads."""

    def rate_limit_status(self) -> dict[str, dict]:
        return {}


def _comic_entry(comic: Comic, **tagged_ids: int) -> dict[str, Any]:
    """One comic of a prompt, with the ids other sources wrote it with."""
    return {
        "pk": comic.pk,
        "path": str(comic.path),
        "tagged_by": list(tagged_ids),
        "tagged_ids": dict(tagged_ids),
    }


def _prompt(
    comics: list[dict[str, Any]],
    *,
    source: str = "comicvine",
    candidates: list[dict[str, Any]] | None = None,
    merge_all_sources: bool = True,
) -> dict[str, Any]:
    """Build a deferred prompt from a Metron-then-Comic Vine run, as cached."""
    return {
        "fingerprint": "fp1",
        "pk": comics[0]["pk"],
        "path": comics[0]["path"],
        "comics": comics,
        "source": source,
        "candidates": candidates
        if candidates is not None
        else [{"issue_id": _COMICVINE_ID, "source": source, "volume_id": _VOLUME_ID}],
        "mode": "auto",
        "formats": ["COMIC_INFO"],
        "delete_original": False,
        "rename": False,
        "source_order": list(_ORDER),
        "merge_all_sources": merge_all_sources,
    }


def _replayed(comic: Comic) -> SimpleNamespace:
    """Build a replay that landed the pick's volume on Comic Vine issue 456."""
    return SimpleNamespace(
        path=Path(comic.path),
        tags=_answer("comicvine", _REPLAYED_ID),
        error=None,
        matched=True,
    )


def _store_issue_id(comic: Comic, source_name: str, issue_id: int) -> None:
    """Give the comic a stored issue id, as the re-import after a write does."""
    source, _ = IdentifierSource.objects.get_or_create(name=source_name)
    identifier = Identifier.objects.create(
        source=source, id_type=IdentifierType.ISSUE.value, key=str(issue_id)
    )
    comic.identifiers.add(identifier)


class MergeAllPromptOrderTests(OnlineTagSessionTestCase):
    """A deferred pick does not overwrite a higher-priority source's tags."""

    @override
    def setUp(self) -> None:
        super().setUp()
        ComicboxTaggingDefaults.objects.filter(pk=1).update(comicvine_key="k")

    def _scan(self, comic: Comic, *, merge_all_sources: bool = True) -> None:
        """
        Scan Metron then Comic Vine: Metron writes, Comic Vine asks.

        The events are comicbox's for one comic of a merge run: the first
        source auto-writes issue 101, the second defers a prompt.
        """
        path = Path(comic.path)
        FakeSession.deferred = [FakeDP(path, "fp1", "comicvine")]
        on_event = self.manager._on_event  # noqa: SLF001

        def _drive(_state, _paths, **_kwargs) -> None:
            for event in (
                SourceStarted(path=path, source="metron"),
                AutoWritten(
                    path=path, source="metron", candidate_summary=str(_METRON_ID)
                ),
                SourceStarted(path=path, source="comicvine"),
                PromptDeferred(path=path, source="comicvine", fingerprint="fp1"),
                FileFinished(path=path, outcome="written"),
            ):
                on_event(event)

        self.manager._pass_runner = double(FakePassRunner(_drive))  # noqa: SLF001
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-merge-order",
            sources=_ORDER,
            merge_all_sources=merge_all_sources,
        )
        with patch(PATCH_TARGET, _ScanSession):
            self.manager.run_session(task)
        assert "fp1" in get_pending_prompts()

    def _patch_for(self, comic: Comic) -> dict[str, Any]:
        """Return the tags the answered prompt queued for ``comic``."""
        (write,) = [task for task in self.write_tasks() if comic.pk in task.comic_pks]
        return write.per_comic_patches[comic.pk]

    def test_a_lower_priority_pick_keeps_the_written_title(self) -> None:
        """
        Metron wrote the comic; answering Comic Vine's prompt keeps its title.

        The state after the scan's write and its re-import: the archive
        carries Metron's tags and the database Metron's issue id.
        """
        comic = make_comic()
        self._scan(comic)
        _write_archive(comic, "title from metron")
        _store_issue_id(comic, "metron", _METRON_ID)
        self.queue.items.clear()

        with _fake_sources():
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        tags = self._patch_for(comic)
        assert tags["title"] == "title from metron"
        # The pick still lands: its id and its keyed tags are in the write.
        assert tags["identifiers"]["comicvine"]["key"] == str(_COMICVINE_ID)
        assert set(tags["genres"]) == {"metron", "comicvine"}

    def test_the_pick_merges_under_what_the_scan_saw_before_its_re_import(
        self,
    ) -> None:
        """
        No stored id yet: the scan's own record of Metron's issue is used.

        The scan writes only once it ends and the re-import follows the
        write, so an answer given mid-scan finds no Metron id in the
        database. The archive still holds the old tags then.
        """
        comic = make_comic()
        self._scan(comic)
        _write_archive(comic, "old title")
        self.queue.items.clear()

        with _fake_sources() as sources:
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert self._patch_for(comic)["title"] == "title from metron"
        assert sources["metron"].get_calls == [_METRON_ID]
        assert sources["comicvine"].get_calls == [_COMICVINE_ID]

    def test_the_prompt_records_the_runs_order_and_what_wrote_its_comic(
        self,
    ) -> None:
        comic = make_comic()
        self._scan(comic)

        prompt = get_pending_prompts()["fp1"]
        assert prompt["source_order"] == list(_ORDER)
        assert prompt["merge_all_sources"] is True
        assert prompt["comics"][0]["tagged_by"] == ["metron"]
        assert prompt["comics"][0]["tagged_ids"] == {"metron": _METRON_ID}

    def test_both_ids_are_pinned_in_the_runs_order(self) -> None:
        """The fetch config lists Metron first, so comicbox lets it win."""
        comic = make_comic()
        self._scan(comic)
        _write_archive(comic, "title from metron")
        _store_issue_id(comic, "metron", _METRON_ID)
        configs: list[ComicboxSettings] = []
        real_build = explicit_id.build_explicit_id_config

        def _recording_build(*args, **kwargs) -> ComicboxSettings:
            settings = real_build(*args, **kwargs)
            configs.append(settings)
            return settings

        with (
            _fake_sources(),
            patch.object(explicit_id, "build_explicit_id_config", _recording_build),
        ):
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        (lookup,) = (settings.online.lookup for settings in configs)
        assert lookup.sources == _ORDER
        assert dict(lookup.ids) == {"metron": _METRON_ID, "comicvine": _COMICVINE_ID}
        assert lookup.first_wins is False

    def test_a_first_wins_run_applies_the_pick_alone(self) -> None:
        comic = make_comic()
        self._scan(comic, merge_all_sources=False)
        _write_archive(comic, "title from metron")
        _store_issue_id(comic, "metron", _METRON_ID)
        self.queue.items.clear()

        with _fake_sources() as sources:
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert self._patch_for(comic)["title"] == "title from comicvine"
        assert sources["metron"].get_calls == []

    def test_a_prompt_cached_before_the_order_applies_the_pick_alone(self) -> None:
        comic = make_comic()
        _write_archive(comic, "title from metron")
        _store_issue_id(comic, "metron", _METRON_ID)
        prompt = _prompt([_comic_entry(comic, metron=_METRON_ID)])
        del prompt["source_order"], prompt["merge_all_sources"]
        set_pending_prompts({"fp1": prompt})

        with _fake_sources() as sources:
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert self._patch_for(comic)["title"] == "title from comicvine"
        assert sources["metron"].get_calls == []

    def test_the_runs_top_source_applies_alone(self) -> None:
        """Metron's own pick has nothing above it to fetch."""
        comic = make_comic()
        _write_archive(comic, "title from comicvine")
        _store_issue_id(comic, "comicvine", _COMICVINE_ID)
        candidates = [{"issue_id": _METRON_ID, "source": "metron"}]
        set_pending_prompts(
            {
                "fp1": _prompt(
                    [_comic_entry(comic, comicvine=_COMICVINE_ID)],
                    source="metron",
                    candidates=candidates,
                )
            }
        )

        with _fake_sources() as sources:
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert self._patch_for(comic)["title"] == "title from metron"
        assert sources["comicvine"].get_calls == []

    def test_a_higher_source_with_no_id_is_never_searched(self) -> None:
        comic = make_comic()
        _write_archive(comic, "old title")
        set_pending_prompts({"fp1": _prompt([_comic_entry(comic)])})

        with _fake_sources() as sources:
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert self._patch_for(comic)["title"] == "title from comicvine"
        assert sources["metron"].get_calls == []
        assert sources["metron"].search_calls == 0

    def test_a_higher_source_without_credentials_now_is_left_out(self) -> None:
        comic = make_comic()
        _write_archive(comic, "title from metron")
        _store_issue_id(comic, "metron", _METRON_ID)
        set_pending_prompts({"fp1": _prompt([_comic_entry(comic, metron=_METRON_ID)])})
        ComicboxTaggingDefaults.objects.filter(pk=1).update(metron_key="")

        with _fake_sources() as sources:
            self.manager.resolve_prompt("fp1", "choose", 0, None)

        assert self._patch_for(comic)["title"] == "title from comicvine"
        assert sources["metron"].get_calls == []

    def test_a_replayed_pick_merges_under_the_higher_source(self) -> None:
        """
        A pick with no issue id replays alone, then merges by the id it found.

        The candidate carries no issue id, so the apply replays the search
        with the answer preloaded and refetches what it landed on.
        """
        comic = make_comic()
        _write_archive(comic, "title from metron")
        _store_issue_id(comic, "metron", _METRON_ID)
        candidates = [{"source": "comicvine", "volume_id": _VOLUME_ID}]
        set_pending_prompts(
            {"fp1": _prompt([_comic_entry(comic)], candidates=candidates)}
        )
        FakeSession.tag_results = [_replayed(comic)]

        with _fake_sources() as sources, patch(APPLY_SESSION_TARGET, FakeSession):
            self.manager.resolve_prompt("fp1", "choose", 0, _VOLUME_ID)

        # The replay itself still ran the pick's source alone.
        assert FakeSession.last_kwargs["sources"] == ("comicvine",)
        tags = self._patch_for(comic)
        assert tags["title"] == "title from metron"
        assert tags["identifiers"]["comicvine"]["key"] == str(_REPLAYED_ID)
        assert sources["metron"].get_calls == [_METRON_ID]
        assert sources["comicvine"].get_calls == [_REPLAYED_ID]

    def test_followers_merge_under_their_own_higher_ids(self) -> None:
        """Each issue of the series refetches the Metron issue it was given."""
        representative, follower = make_series_comics(2)
        for comic in (representative, follower):
            _write_archive(comic, "title from metron")
        follower_metron_id = _METRON_ID + 1
        set_pending_prompts(
            {
                "fp1": _prompt(
                    [
                        _comic_entry(representative, metron=_METRON_ID),
                        _comic_entry(follower, metron=follower_metron_id),
                    ]
                )
            }
        )
        FakeSession.tag_results = [_replayed(follower)]

        with _fake_sources() as sources, patch(APPLY_SESSION_TARGET, FakeSession):
            self.manager.resolve_prompt("fp1", "choose", 0, _VOLUME_ID)

        for comic in (representative, follower):
            assert self._patch_for(comic)["title"] == "title from metron"
        assert sources["metron"].get_calls == [_METRON_ID, follower_metron_id]
        assert sources["comicvine"].get_calls == [_COMICVINE_ID, _REPLAYED_ID]

    def test_a_drifted_replay_requeues_with_the_runs_order(self) -> None:
        """No merge fetch, no write, and the fresh prompt keeps the order."""
        comic = make_comic()
        _write_archive(comic, "title from metron")
        candidates = [{"source": "comicvine", "volume_id": _VOLUME_ID}]
        set_pending_prompts(
            {
                "fp1": _prompt(
                    [_comic_entry(comic, metron=_METRON_ID)], candidates=candidates
                )
            }
        )
        FakeSession.tag_results = [
            SimpleNamespace(path=Path(comic.path), tags={}, error=None, matched=False)
        ]
        FakeSession.deferred = [FakeDP(Path(comic.path), "fp2", "comicvine")]

        with _fake_sources() as sources, patch(APPLY_SESSION_TARGET, FakeSession):
            self.manager.resolve_prompt("fp1", "choose", 0, _VOLUME_ID)

        assert self.write_tasks() == []
        assert sources["metron"].get_calls == []
        fresh = get_pending_prompts()["fp2"]
        assert fresh["source_order"] == list(_ORDER)
        assert fresh["merge_all_sources"] is True
        assert fresh["comics"][0]["tagged_ids"] == {"metron": _METRON_ID}

    def test_a_failed_merge_fetch_still_writes_the_replayed_pick(self) -> None:
        """The pick is never lost to the refetch; it is written as replayed."""
        comic = make_comic()
        _store_issue_id(comic, "metron", _METRON_ID)
        candidates = [{"source": "comicvine", "volume_id": _VOLUME_ID}]
        set_pending_prompts(
            {"fp1": _prompt([_comic_entry(comic)], candidates=candidates)}
        )
        FakeSession.tag_results = [_replayed(comic)]

        def _unreachable(*_args, **_kwargs) -> None:
            reason = "network down"
            raise OSError(reason)

        with (
            patch(APPLY_SESSION_TARGET, FakeSession),
            patch(APPLY_FETCH_TARGET, _unreachable),
        ):
            self.manager.resolve_prompt("fp1", "choose", 0, _VOLUME_ID)

        assert self._patch_for(comic)["title"] == "title from comicvine"


class MatchedIdTests(SimpleTestCase):
    """The scan notes the issue id each source auto-wrote a comic with."""

    _PATH: Final = Path("/comics/c1.cbz")

    def test_each_source_records_its_issue_id(self) -> None:
        stats = OnlineTagOutcomeStats()
        for source, summary in (("metron", "101"), ("comicvine", "4000-202")):
            stats.record(
                AutoWritten(path=self._PATH, source=source, candidate_summary=summary)
            )
        assert stats.matched_ids_by_path == {
            self._PATH: {"metron": 101, "comicvine": 202}
        }

    def test_a_summary_that_is_not_an_id_records_none(self) -> None:
        stats = OnlineTagOutcomeStats()
        stats.record(
            AutoWritten(path=self._PATH, source="metron", candidate_summary="Foo #1")
        )
        assert stats.matched_ids_by_path == {}
        assert stats.matched_source_by_path == {self._PATH: ["metron"]}
