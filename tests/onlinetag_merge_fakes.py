"""
Fake online sources and cached prompts for tests of the merge order.

comicbox merges the sources one lookup queried, the first-listed source
winning every single-valued tag they disagree on. These fakes stand in for
the APIs, so the tests run comicbox's real merge on a real archive and
nothing leaves the process.
"""

from __future__ import annotations

import zipfile
from contextlib import contextmanager
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import TYPE_CHECKING, Any, Final
from unittest.mock import patch

from comicbox.box.online_lookup import ONLINE_SOURCE_BY_NAME, ComicboxOnlineLookup
from comicbox.formats import MetadataFormats

if TYPE_CHECKING:
    from collections.abc import Generator

    from codex.models import Comic

ORDER: Final = ("metron", "comicvine")
METRON_ID: Final = 101
# FakeDP's one candidate.
COMICVINE_ID: Final = 123
# Where a replay lands: another Comic Vine issue of the picked volume.
REPLAYED_ID: Final = 456
VOLUME_ID: Final = 5


def answer(name: str, issue_id: int) -> dict[str, Any]:
    """One source's answer: a single-valued tag, a keyed tag and its own id."""
    return {
        "title": f"title from {name}",
        "genres": {name: {}},
        "identifiers": {name: {"key": str(issue_id)}},
    }


class FakeSource:
    """An online source that answers ``get`` from memory and records it."""

    def __init__(self, name: str) -> None:
        """Answer as ``name``, in comicbox's own schema."""
        self.name = name
        self.metadata_source = ONLINE_SOURCE_BY_NAME[name]
        self.metadata_format = MetadataFormats.COMICBOX_JSON
        self.get_calls: list[int] = []
        self.search_calls = 0
        # Ids the API rejects, as it does a wrong or deleted issue.
        self.failing: set[int] = set()

    def is_configured(self) -> bool:
        return True

    def get(self, issue_id: int) -> dict[str, Any]:
        self.get_calls.append(issue_id)
        if issue_id in self.failing:
            reason = f"{self.name} has no issue {issue_id}"
            raise LookupError(reason)
        return answer(self.name, issue_id)

    def search(self, _profile) -> list:
        self.search_calls += 1
        return []


@contextmanager
def fake_sources() -> Generator[dict[str, FakeSource]]:
    """Have every comicbox lookup in the block build these sources."""
    sources = {name: FakeSource(name) for name in ONLINE_SOURCE_BY_NAME}
    factories = MappingProxyType(
        {
            name: (lambda _creds, _settings, source=source: source)
            for name, source in sources.items()
        }
    )
    with patch.object(ComicboxOnlineLookup, "_ONLINE_SOURCE_FACTORIES", factories):
        yield sources


def write_archive(comic: Comic, title: str) -> None:
    """Make the comic a real archive whose ComicInfo carries ``title``."""
    fields = f"<Series>S</Series><Number>1</Number><Title>{title}</Title>"
    with zipfile.ZipFile(comic.path, "w") as zf:
        zf.writestr("ComicInfo.xml", f"<ComicInfo>{fields}</ComicInfo>")


def comic_entry(comic: Comic, **tagged_ids: int) -> dict[str, Any]:
    """One comic of a prompt, with the ids other sources wrote it with."""
    return {
        "pk": comic.pk,
        "path": str(comic.path),
        "tagged_by": list(tagged_ids),
        "tagged_ids": dict(tagged_ids),
    }


def make_prompt(
    comics: list[dict[str, Any]],
    *,
    fingerprint: str = "fp1",
    source: str = "comicvine",
    candidates: list[dict[str, Any]] | None = None,
    merge_all_sources: bool = True,
) -> dict[str, Any]:
    """Build a deferred prompt from a Metron-then-Comic Vine run, as cached."""
    return {
        "fingerprint": fingerprint,
        "pk": comics[0]["pk"],
        "path": comics[0]["path"],
        "comics": comics,
        "source": source,
        "candidates": candidates
        if candidates is not None
        else [{"issue_id": COMICVINE_ID, "source": source, "volume_id": VOLUME_ID}],
        "mode": "auto",
        "formats": ["COMIC_INFO"],
        "delete_original": False,
        "rename": False,
        "source_order": list(ORDER),
        "merge_all_sources": merge_all_sources,
    }


def replayed(comic: Comic) -> SimpleNamespace:
    """Build a replay that landed the pick's volume on Comic Vine issue 456."""
    return SimpleNamespace(
        path=Path(comic.path),
        tags=answer("comicvine", REPLAYED_ID),
        error=None,
        matched=True,
    )
