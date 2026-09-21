"""
Shared doubles for the online tagging session manager tests.

Every manager test drives the same seam: a fake ``OnlineSession`` standing in
for comicbox, a fake librarian queue collecting the tasks the manager enqueues,
and one real comic row backed by a file on disk. They live here so each test
module can stay about one behavior of the manager.
"""

from __future__ import annotations

import shutil
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, ClassVar, Final, override

from django.core.cache import caches
from django.test import TestCase
from loguru import logger

from codex.librarian.onlinetag.session_manager import OnlineTagSessionManager
from codex.librarian.onlinetag.status import OnlineLookupStatus
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import (
    Comic,
    ComicboxTaggingDefaults,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from tests.tmp_dirs import tmp_dir

if TYPE_CHECKING:
    from pathlib import Path

TMP_DIR: Final = tmp_dir("codex.tests.onlinetag.manager")
# The manager runs the scan; the applier writes an answered prompt. Both call
# the same two collaborators, and a patch only takes where the caller looks
# them up — so each has its own name here rather than one shared by habit.
PATCH_TARGET: Final = "codex.librarian.onlinetag.session_manager.OnlineSession"
FETCH_TARGET: Final = (
    "codex.librarian.onlinetag.session_manager.fetch_tags_by_explicit_id"
)
APPLY_SESSION_TARGET: Final = "codex.librarian.onlinetag.prompt_apply.OnlineSession"
APPLY_FETCH_TARGET: Final = (
    "codex.librarian.onlinetag.prompt_apply.fetch_tags_by_explicit_id"
)


def double(stub: object) -> Any:
    """
    Pass a test double through a strictly-typed seam.

    The manager's constructor and ``_pass_runner`` attribute are annotated
    with concrete production types (loguru ``Logger``, multiprocessing
    ``Queue``, ``TagPassRunner``). These fakes only implement the slice the
    tests exercise, so erase to ``Any`` at the injection point instead of
    weakening the production annotations.
    """
    return stub


class FakeQueue:
    """Collects everything put on it for assertions."""

    def __init__(self) -> None:
        """Start with nothing queued."""
        self.items: list = []

    def put(self, item) -> None:
        self.items.append(item)


class FakePassRunner:
    """
    Stand-in for TagPassRunner with Pass 1 stubbed out.

    Models the whole seam the manager reaches through, not just
    ``collect_results``: ``_on_event`` also reads the live status and releases
    a source's retry deadline when that source reports an outcome.
    """

    def __init__(self, collect_results=None) -> None:
        """Wire an optional pass body; default is a no-op pass."""
        self.collect_results = collect_results or (lambda *_args, **_kwargs: None)
        self.source_retry_at: dict[str, float] = {}
        self.lookup_status = None
        self.rate_limited = False

    def begin_status(self, total: int) -> OnlineLookupStatus:
        """Open the scan's status row the way the real runner does."""
        status = OnlineLookupStatus()
        status.total = total
        status.complete = 0
        self.lookup_status = status
        return status

    def finish_status(self) -> None:
        """Drop the row the prepass opened."""
        self.lookup_status = None


class FakeCandidate:
    """One search hit a deferred prompt offers the admin."""

    def __init__(self, issue_id: int, source: str) -> None:
        """Build a candidate with a summary the admin panel can render."""
        self.issue_id = issue_id
        self.source = source
        self.score = 0.9
        self.url = ""
        self.summary = SimpleNamespace(
            series="S", issue="1", year=2020, publisher="P", cover_url=""
        )


class FakeDP:
    """An ambiguous match comicbox defers back to the caller."""

    def __init__(self, path: Path, fingerprint: str, source: str) -> None:
        """Build a deferred prompt offering one candidate."""
        self.path = path
        self.fingerprint = fingerprint
        self.source = source
        self.match = "auto"
        self.candidates = [FakeCandidate(123, source)]


class FakeSession:
    """Stand-in for comicbox.OnlineSession driven by class-level fixtures."""

    deferred: ClassVar[list] = []
    tag_results: ClassVar[list] = []
    preloaded: ClassVar[list] = []
    last_kwargs: ClassVar[dict] = {}

    def __init__(self, **kwargs) -> None:
        """Record the kwargs the manager built the session with."""
        self.kwargs = kwargs
        FakeSession.last_kwargs = kwargs

    def tag_many(self, paths):  # noqa: ARG002
        return iter(FakeSession.tag_results)

    def deferred_prompts(self):
        return list(FakeSession.deferred)

    def preload_resolution(
        self, fingerprint, *, action, payload=None, chosen_volume_id=None
    ) -> None:
        FakeSession.preloaded.append((fingerprint, action, payload, chosen_volume_id))

    def cancel(self) -> None:
        pass


def _make_series() -> dict[str, Any]:
    """Create (or reuse) the one library and series every test comic sits in."""
    TMP_DIR.mkdir(exist_ok=True, parents=True)
    library, _ = Library.objects.get_or_create(path=str(TMP_DIR))
    publisher, _ = Publisher.objects.get_or_create(name="P")
    imprint, _ = Imprint.objects.get_or_create(name="I", publisher=publisher)
    series, _ = Series.objects.get_or_create(
        name="S", publisher=publisher, imprint=imprint
    )
    volume, _ = Volume.objects.get_or_create(
        name="1", publisher=publisher, imprint=imprint, series=series
    )
    return {
        "library": library,
        "publisher": publisher,
        "imprint": imprint,
        "series": series,
        "volume": volume,
    }


def make_comic(name: str = "c", issue_number: int = 1) -> Comic:
    """Create one comic row whose path exists on disk."""
    path = TMP_DIR / f"{name}.cbz"
    groups = _make_series()
    path.touch()
    return Comic.objects.create(
        path=path,
        issue_number=issue_number,
        name=name,
        size=1,
        file_type="CBZ",
        **groups,
    )


def make_series_comics(count: int) -> list[Comic]:
    """
    Create ``count`` issues of one series, as a series-wide tag run sees them.

    Comicbox raises ONE deferred prompt for a whole series, so anything about
    answering prompts needs more than one issue of the same series to be
    testing the real shape of the problem.
    """
    return [
        make_comic(name=f"c{issue}", issue_number=issue)
        for issue in range(1, count + 1)
    ]


class OnlineTagSessionTestCase(TestCase):
    """A fresh manager wired to a fake queue, with the class fixtures reset."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()
        FakeSession.deferred = []
        FakeSession.tag_results = []
        FakeSession.preloaded = []
        FakeSession.last_kwargs = {}
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1,
            defaults={"metron_key": "t"},
        )
        self.queue = FakeQueue()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.manager = OnlineTagSessionManager(  # pyright: ignore[reportUninitializedInstanceVariable]
            double(logger),
            double(self.queue),
            thread_queue=None,
        )

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def write_tasks(self) -> list[BulkTagWriteTask]:
        """Every tag write task the manager enqueued."""
        return [i for i in self.queue.items if isinstance(i, BulkTagWriteTask)]
