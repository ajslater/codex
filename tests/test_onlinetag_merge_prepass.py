"""
B20, left for a ruling: under Merge all sources, a newly keyed source is never asked.

The stored-id prepass takes a comic out of the run when any selected source
has its id, so the search pass, the only place a source without a stored id
is asked, never sees it. On an already-tagged library, adding a VerseDB key
and re-running with Merge all sources fetches Metron by id and never asks
VerseDB. Changing that changes how many API calls a re-tag makes, which is
AJ's call; this test states the behaviour the tab promises and is expected
to fail until then.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from comicbox.formats.comicbox.schema import IDENTIFIERS_KEY
from comicbox.identifiers import ID_KEY_KEY

from codex.librarian.onlinetag.session_state import SessionState
from codex.librarian.onlinetag.tasks import BulkOnlineTagTask
from codex.models import ComicboxTaggingDefaults, Identifier, IdentifierSource
from tests.onlinetag_session_fakes import (
    FETCH_TARGET,
    FakeSession,
    OnlineTagSessionTestCase,
    double,
    make_comic,
)


class MergeAllPrepassTests(OnlineTagSessionTestCase):
    """Every enabled source is queried, as the Tagging tab says."""

    @pytest.mark.xfail(
        strict=True,
        reason="B20: the prepass drops a comic any source has an id for; AJ to rule",
    )
    def test_a_source_without_a_stored_id_is_still_asked(self) -> None:
        """The comic stays in the run for VerseDB, which has no stored id."""
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
        fetched = {"series": "X", IDENTIFIERS_KEY: {"metron": {ID_KEY_KEY: "123495"}}}

        with patch(FETCH_TARGET, lambda *_a, **_k: fetched):
            self.manager._prefetch_stored_ids(  # noqa: SLF001
                state, comic_paths, task, credentials
            )

        # Left for the search pass, which is where VerseDB would be asked.
        assert comic_paths == {comic.pk: path}
