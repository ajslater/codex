"""
Merging a second scan into a running online-tag session.

A second ``BulkOnlineTagTask`` enqueued mid-scan is merged into the live
session. Comics the session already holds must be recognized, or a scan
whose selection overlaps (re-picking a folder to catch additions is the
natural gesture) queues them twice: inflated totals and duplicate lookups
against rate-limited sources.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from codex.librarian.onlinetag.session_state import SessionState
from codex.librarian.onlinetag.tasks import BulkOnlineTagTask
from codex.models import Comic
from tests.onlinetag_session_fakes import (
    FakeSession,
    OnlineTagSessionTestCase,
    double,
    make_comic,
)

#: The comic the session already holds, plus the one merged into it.
_HELD_PLUS_NEW: Final = 2


class MergeTaskTests(OnlineTagSessionTestCase):
    """_merge_task adds only comics the session isn't already tagging."""

    def _state_holding(self, comic) -> SessionState:
        """Build a session state that already carries ``comic``."""
        return SessionState(
            session=double(FakeSession()),
            path_to_pk={Path(comic.path): comic.pk},
            total_comics=1,
        )

    def test_already_queued_comic_is_not_merged_again(self) -> None:
        """An overlapping selection must not re-queue a comic."""
        comic = make_comic()
        state = self._state_holding(comic)
        task = BulkOnlineTagTask(comic_pks=frozenset({comic.pk}), session_id="s")

        self.manager._merge_task(state, task)  # noqa: SLF001

        assert state.total_comics == 1
        assert state.pending_paths == []
        assert state.path_to_pk == {Path(comic.path): comic.pk}

    @staticmethod
    def _sibling_of(comic: Comic) -> Comic:
        """Create a second comic in the same library as ``comic``."""
        path = Path(comic.path).parent / "d.cbz"
        path.touch()
        return Comic.objects.create(
            library=comic.library,
            path=path,
            issue_number=2,
            name="d",
            publisher=comic.publisher,
            imprint=comic.imprint,
            series=comic.series,
            volume=comic.volume,
            size=1,
            file_type="CBZ",
        )

    def test_new_comic_is_merged(self) -> None:
        """A comic the session doesn't hold is queued and counted."""
        held = make_comic()
        state = self._state_holding(held)
        new_comic = self._sibling_of(held)
        task = BulkOnlineTagTask(comic_pks=frozenset({new_comic.pk}), session_id="s")

        self.manager._merge_task(state, task)  # noqa: SLF001

        assert state.total_comics == _HELD_PLUS_NEW
        assert state.pending_paths == [Path(new_comic.path)]
        assert state.path_to_pk[Path(new_comic.path)] == new_comic.pk
