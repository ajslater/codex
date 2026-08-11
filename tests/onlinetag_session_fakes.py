"""
Shared doubles for the online tagging session manager tests.

Every manager test drives the same seam: a fake ``OnlineSession`` standing in
for comicbox, a fake librarian queue collecting the tasks the manager enqueues,
and one real comic row backed by a file on disk. They live here so each test
module can stay about one behavior of the manager.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, Final, override

from django.core.cache import caches
from django.test import TestCase
from loguru import logger

from codex.librarian.onlinetag.session_manager import OnlineTagSessionManager
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

TMP_DIR: Final = Path("/tmp/codex.tests.onlinetag.manager")  # noqa: S108
PATCH_TARGET: Final = "codex.librarian.onlinetag.session_manager.OnlineSession"
FETCH_TARGET: Final = (
    "codex.librarian.onlinetag.session_manager.fetch_tags_by_explicit_id"
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
        self.mode = "auto"
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


def make_comic() -> Comic:
    """Create one comic row whose path exists on disk."""
    TMP_DIR.mkdir(exist_ok=True, parents=True)
    library = Library.objects.create(path=str(TMP_DIR))
    publisher = Publisher.objects.create(name="P")
    imprint = Imprint.objects.create(name="I", publisher=publisher)
    series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
    volume = Volume.objects.create(
        name="1", publisher=publisher, imprint=imprint, series=series
    )
    path = TMP_DIR / "c.cbz"
    path.touch()
    return Comic.objects.create(
        library=library,
        path=path,
        issue_number=1,
        name="c",
        publisher=publisher,
        imprint=imprint,
        series=series,
        volume=volume,
        size=1,
        file_type="CBZ",
    )


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
