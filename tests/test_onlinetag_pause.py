"""
Pause stops a scan while it is busy, not only between search results.

The online tag thread reads its queue between search results, so a Pause
waited out the whole stored-id prepass, which on a re-tag is the whole run,
and any rate-limit wait in it. The daemon now hands the Pause to the scan as
it arrives; the prepass stops before its next comic, and its retry wait
wakes on the Pause, as the search pass's already does.

A Pause only asks comicbox to stop. A lookup already under way runs to its
end, outside a retry wait, and reports what it found, so the search pass
keeps that result before it stops.
"""

import time
from pathlib import Path
from types import SimpleNamespace
from typing import override
from unittest.mock import MagicMock, patch

import pytest
from comicbox.events import AutoWritten, FileFinished, SourceStarted
from comicbox.exceptions import OnlineLookupAbortedError

from codex.librarian.librariand import LibrarianDaemon
from codex.librarian.onlinetag.session_snapshot import get_resume_state
from codex.librarian.onlinetag.session_state import SessionState
from codex.librarian.onlinetag.tasks import BulkOnlineTagTask, OnlineTagAbortTask
from codex.models import Comic, Identifier, IdentifierSource
from tests.onlinetag_session_fakes import (
    FETCH_TARGET,
    PATCH_TARGET,
    FakeSession,
    OnlineTagSessionTestCase,
    double,
    make_comic,
    make_series_comics,
)

_SESSION_ID = "scan"
# A rate-limit wait long enough that waiting it out would fail the test.
_LONG_WAIT = 60.0


class PrepassPauseTests(OnlineTagSessionTestCase):
    """A Pause during the stored-id prepass stops it."""

    def _identified(self, count: int) -> list[Comic]:
        """Make ``count`` comics, each with a stored Metron issue id."""
        first = make_comic()
        comics = [first]
        source, _ = IdentifierSource.objects.get_or_create(name="metron")
        for number in range(2, count + 1):
            path = Path(first.path).parent / f"c{number}.cbz"
            path.touch()
            comics.append(
                Comic.objects.create(
                    library=first.library,
                    path=path,
                    issue_number=number,
                    name=f"c{number}",
                    publisher=first.publisher,
                    imprint=first.imprint,
                    series=first.series,
                    volume=first.volume,
                    size=1,
                    file_type="CBZ",
                )
            )
        for number, comic in enumerate(comics, start=1):
            identifier = Identifier.objects.create(
                source=source, id_type="comic", key=str(1000 + number)
            )
            comic.identifiers.add(identifier)
        return comics

    def _prefetch(self, comics: list[Comic], fetch) -> dict[int, Path]:
        comic_paths = {comic.pk: Path(comic.path) for comic in comics}
        state = SessionState(
            session=double(FakeSession()),
            path_to_pk={path: pk for pk, path in comic_paths.items()},
            sources=("metron",),
        )
        self.manager._sessions[_SESSION_ID] = state  # noqa: SLF001
        task = BulkOnlineTagTask(
            comic_pks=frozenset(comic_paths),
            session_id=_SESSION_ID,
            sources=("metron",),
        )
        credentials = self.manager._build_credentials()  # noqa: SLF001
        assert credentials is not None
        with patch(FETCH_TARGET, fetch):
            self.manager._prefetch_stored_ids(  # noqa: SLF001
                state, comic_paths, task, credentials
            )
        return comic_paths

    def test_the_prepass_stops_at_the_next_comic(self) -> None:
        """Paused during the first fetch, the other two are never fetched."""
        comics = self._identified(3)
        fetched = []

        def fetch(path, *_args, **_kwargs):
            fetched.append(path)
            self.manager.cancel_session(_SESSION_ID)
            return {"series": "X"}

        comic_paths = self._prefetch(comics, fetch)
        assert len(fetched) == 1
        # The two it never reached stay for Resume.
        assert len(comic_paths) == len(comics) - 1

    def test_a_rate_limit_wait_wakes_on_pause(self) -> None:
        """The fetch's retry wait ends as soon as the scan is paused."""
        comics = self._identified(1)
        waits = []

        def fetch(_path, *_args, retry_sleep=None, **_kwargs):
            assert retry_sleep is not None, "the prepass fetch has no Pause-aware wait"
            self.manager.cancel_session(_SESSION_ID)
            start = time.monotonic()
            with pytest.raises(OnlineLookupAbortedError):
                retry_sleep(_LONG_WAIT)
            waits.append(time.monotonic() - start)

        self._prefetch(comics, fetch)
        assert waits
        assert waits[0] < _LONG_WAIT / 10


class SearchPassPauseTests(OnlineTagSessionTestCase):
    """A Pause during a search keeps the lookup that was under way."""

    def test_a_lookup_that_finishes_after_a_pause_is_written(self) -> None:
        """
        Written, counted, and out of the resume set; the rest stay in it.

        comicbox's ``cancel()`` sets an event. The lookup in flight runs on,
        writes its comic and reports it written; only the paths after it
        come back cancelled.
        """
        comics = make_series_comics(3)
        manager = self.manager
        finished: list[Path] = []

        class _FinishesAfterPause(FakeSession):
            def rate_limit_status(self) -> dict[str, dict]:
                return {}

            @override
            def tag_many(self, paths):
                first, *rest = paths
                on_event = self.kwargs["on_event"]
                on_event(SourceStarted(path=first, source="metron"))
                manager.cancel_session(_SESSION_ID)
                on_event(
                    AutoWritten(path=first, source="metron", candidate_summary="101")
                )
                on_event(FileFinished(path=first, outcome="written"))
                finished.append(first)
                yield SimpleNamespace(
                    path=first,
                    tags={"series": "S"},
                    matched=True,
                    error=None,
                    cancelled=False,
                )
                for path in rest:
                    yield SimpleNamespace(path=path, cancelled=True)

        task = BulkOnlineTagTask(
            comic_pks=frozenset(comic.pk for comic in comics),
            session_id=_SESSION_ID,
            sources=("metron",),
        )
        with patch(PATCH_TARGET, _FinishesAfterPause):
            manager.run_session(task)

        (path,) = finished
        pk_by_path = {Path(comic.path): comic.pk for comic in comics}
        written = {pk for t in self.write_tasks() for pk in t.per_comic_patches}
        assert written == {pk_by_path[path]}
        resume = get_resume_state()
        assert resume is not None
        assert set(resume["remaining_pks"]) == set(pk_by_path.values()) - written


def test_the_daemon_delivers_a_pause_at_once() -> None:
    """The daemon cancels the scan itself, not only through the busy queue."""
    thread = MagicMock()
    daemon = SimpleNamespace(_threads=SimpleNamespace(online_tag_thread=thread))
    task = OnlineTagAbortTask(session_id=_SESSION_ID)
    assert LibrarianDaemon._requeue(daemon, task)  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]  # noqa: SLF001
    thread.cancel_session.assert_called_once_with(_SESSION_ID)
    # Still queued, for a scan that starts after it.
    thread.queue.put.assert_called_once_with(task)
