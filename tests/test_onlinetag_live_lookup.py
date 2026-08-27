"""
Unit tests for the live "Looking up" state the admin status table renders.

The table's per-source ``in_flight`` cell used to be unreachable: the fold set
it on ``SearchStarted`` and cleared it on ``FileFinished``, and comicbox emits
both before ``tag_many`` yields — the only moment the daemon published. So
every publish sampled the one instant when no lookup was recorded, and comics
appeared to jump straight from Queued to Matched.

Liveness is now a marker on the scan (:class:`LiveLookup`), set from the event
stream and from the stored-id prepass, published on its own forced call site,
and projected into the snapshot at build time. These tests cover the daemon
half: the marker's own contract, when a publish and its notification fire, and
that a display path can never corrupt a comic's outcome. The projection into
snapshot rows is covered by ``test_onlinetag_snapshot``.
"""

from __future__ import annotations

from pathlib import Path
from typing import override
from unittest.mock import patch

from comicbox.events import (
    FileError,
    FileFinished,
    SearchStarted,
    SourceStarted,
)

from codex.librarian.notifier.tasks import ONLINE_TAG_SNAPSHOT_TASK
from codex.librarian.onlinetag.session_snapshot import get_snapshot
from codex.librarian.onlinetag.session_state import LiveLookup, SessionState
from codex.librarian.onlinetag.statuses import IN_FLIGHT
from tests.onlinetag_session_fakes import (
    FakePassRunner,
    OnlineTagSessionTestCase,
    double,
)

_A = Path("/c/a.cbz")
_B = Path("/c/b.cbz")
_TWO = 2


class LiveLookupMarkerTests(OnlineTagSessionTestCase):
    """The marker's own contract."""

    def test_begin_records_the_pair(self) -> None:
        live = LiveLookup()
        live.begin(_A, "metron")
        assert (live.path, live.source) == (_A, "metron")

    def test_end_clears_the_current_comic(self) -> None:
        live = LiveLookup()
        live.begin(_A, "metron")
        live.end(_A)
        assert (live.path, live.source) == (None, "")

    def test_end_ignores_a_comic_that_is_not_current(self) -> None:
        """A late FileFinished for a prior comic must not wipe this one."""
        live = LiveLookup()
        live.begin(_B, "comicvine")
        live.end(_A)
        assert (live.path, live.source) == (_B, "comicvine")


class LiveLookupPublishTests(OnlineTagSessionTestCase):
    """When the daemon publishes and announces the live marker."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.manager._pass_runner = double(FakePassRunner())  # noqa: SLF001
        self.state = SessionState(  # pyright: ignore[reportUninitializedInstanceVariable]
            session=None,  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]
            path_to_pk={_A: 1, _B: 2},
            sources=("metron", "comicvine"),
            total_comics=2,
        )
        self.manager._sessions["sid"] = self.state  # noqa: SLF001
        self.manager._active_session_id = "sid"  # noqa: SLF001

    def _notifications(self) -> list:
        return [i for i in self.queue.items if i is ONLINE_TAG_SNAPSHOT_TASK]

    def test_source_started_publishes_a_live_snapshot(self) -> None:
        """The whole point: a published snapshot carries the live cell."""
        self.manager._on_event(SourceStarted(path=_A, source="metron"))  # noqa: SLF001

        snap = get_snapshot()
        assert snap is not None
        row = next(r for r in snap["comics"] if r["pk"] == 1)
        assert row["status"] == IN_FLIGHT
        assert row["source_statuses"] == {"metron": IN_FLIGHT}

    def test_source_started_announces_the_snapshot(self) -> None:
        """Without its own message the browser would not know to refetch."""
        self.manager._on_event(SourceStarted(path=_A, source="metron"))  # noqa: SLF001
        assert len(self._notifications()) == 1

    def test_every_publish_announces_itself(self) -> None:
        """
        The boundary publish needs a notification too.

        It used to ride ``task.progress``, which the client no longer answers
        with a snapshot fetch — so without its own announcement the table
        would freeze between comics.
        """
        self.manager._publish_snapshot(self.state, force=True)  # noqa: SLF001
        assert len(self._notifications()) == 1

    def test_a_throttled_publish_announces_nothing(self) -> None:
        """Nothing was written, so there is nothing to tell the client about."""
        self.manager._publish_snapshot(self.state, force=True)  # noqa: SLF001
        self.manager._publish_snapshot(self.state)  # noqa: SLF001
        assert len(self._notifications()) == 1

    def test_search_started_also_drives_the_marker(self) -> None:
        """Kept as the fallback for a comicbox too old to emit SourceStarted."""
        self.manager._on_event(SearchStarted(path=_B, source="comicvine"))  # noqa: SLF001
        assert (self.state.live.path, self.state.live.source) == (_B, "comicvine")

    def test_the_source_started_search_started_pair_publishes_once(self) -> None:
        """A cold search emits both; the (path, source) dedupe collapses them."""
        self.manager._on_event(SourceStarted(path=_A, source="metron"))  # noqa: SLF001
        self.manager._on_event(SearchStarted(path=_A, source="metron"))  # noqa: SLF001
        assert len(self._notifications()) == 1

    def test_file_finished_clears_the_marker(self) -> None:
        self.manager._on_event(SourceStarted(path=_A, source="metron"))  # noqa: SLF001
        self.manager._on_event(FileFinished(path=_A, outcome="written"))  # noqa: SLF001
        assert self.state.live.path is None

    def test_file_error_clears_the_marker(self) -> None:
        self.manager._on_event(SourceStarted(path=_A, source="metron"))  # noqa: SLF001
        self.manager._on_event(FileError(path=_A, error="boom"))  # noqa: SLF001
        assert self.state.live.path is None

    def test_a_stale_file_finished_leaves_the_current_comic_alone(self) -> None:
        """A late event for an earlier comic must not blank the live row."""
        self.manager._on_event(SourceStarted(path=_B, source="metron"))  # noqa: SLF001
        self.manager._on_event(FileFinished(path=_A, outcome="written"))  # noqa: SLF001
        assert self.state.live.path == _B

    def test_a_path_less_source_started_is_ignored(self) -> None:
        self.manager._on_event(SourceStarted(path=None, source="metron"))  # noqa: SLF001
        assert self.state.live.path is None
        assert not self._notifications()

    def test_source_started_without_an_active_session_writes_nothing(self) -> None:
        self.manager._active_session_id = None  # noqa: SLF001
        self.manager._on_event(SourceStarted(path=_A, source="metron"))  # noqa: SLF001
        assert get_snapshot() is None
        assert not self._notifications()

    def test_the_live_publish_leaves_the_boundary_throttle_alone(self) -> None:
        """
        A forced live publish must not stamp the shared throttle clock.

        The result-boundary publish — which carries the comic's terminal
        status and narrows the resume descriptor — is unforced. If a live
        publish reset the 4s window, every comic whose lookup came back
        inside it would lose its terminal publish entirely.
        """
        before = self.manager._last_publish  # noqa: SLF001
        self.manager._on_event(SourceStarted(path=_A, source="metron"))  # noqa: SLF001
        assert self.manager._last_publish == before  # noqa: SLF001

    def test_the_live_publish_does_not_rewrite_the_resume_descriptor(self) -> None:
        """
        Skip the resume write on a live publish.

        The remainder can only shrink before the next boundary publish, which
        rewrites it — so skipping the write costs at most one comic of
        staleness and saves a second file write per lookup.
        """
        target = "codex.librarian.onlinetag.session_manager.set_resume_state"
        with patch(target) as set_resume:
            self.manager._on_event(SourceStarted(path=_A, source="metron"))  # noqa: SLF001
        set_resume.assert_not_called()

    def test_a_burst_of_live_publishes_is_floored(self) -> None:
        """
        Floor a burst of live publishes.

        Comicbox answers a search from its on-disk HTTP cache when it can, so
        on a re-scan the events fire at CPU speed with no network pacing them.
        The floor is what keeps that from hammering the cache and the sockets.
        """
        self.manager._on_event(SourceStarted(path=_A, source="metron"))  # noqa: SLF001
        self.manager._on_event(SourceStarted(path=_B, source="metron"))  # noqa: SLF001
        assert len(self._notifications()) == 1

    def test_the_floor_lapses(self) -> None:
        """A lookup slower than the floor still gets its own frame."""
        self.manager._on_event(SourceStarted(path=_A, source="metron"))  # noqa: SLF001
        self.manager._last_live_publish -= self.manager._LIVE_PUBLISH_DELTA  # noqa: SLF001
        self.manager._on_event(SourceStarted(path=_B, source="metron"))  # noqa: SLF001
        assert len(self._notifications()) == _TWO

    def test_a_raising_queue_put_cannot_error_the_comic(self) -> None:
        """
        Swallow a queue failure rather than erroring the comic.

        The emit sits before comicbox's own try, so an escape becomes a
        FileError — and _row_source_statuses fills every column with ERROR.
        A status display must never be able to corrupt an outcome.
        """

        class _Exploding:
            def put(self, _item) -> None:
                msg = "queue closed"
                raise RuntimeError(msg)

        self.manager.librarian_queue = double(_Exploding())
        # Must not raise.
        self.manager._on_event(SourceStarted(path=_A, source="metron"))  # noqa: SLF001
        assert _A not in self.state.stats.errored_paths
