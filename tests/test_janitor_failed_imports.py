"""Unit tests for Janitor.force_update_all_failed_imports logging."""

from __future__ import annotations

from contextlib import contextmanager
from multiprocessing import Event
from threading import Lock
from typing import TYPE_CHECKING, override

from django.test import TestCase
from loguru import logger

from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.models import FailedImport, Library

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def _capture_logs() -> Iterator[list[str]]:
    """Collect loguru INFO+ messages emitted inside the ``with`` block."""
    records: list[str] = []
    sink_id = logger.add(records.append, level="INFO", format="{message}")
    try:
        yield records
    finally:
        logger.remove(sink_id)


class _FakeQueue:
    """Record tasks put on the librarian queue without touching multiprocessing."""

    def __init__(self) -> None:
        self.items: list = []

    def put(self, item) -> None:
        self.items.append(item)


class ForceUpdateFailedImportsTests(TestCase):
    """force_update_all_failed_imports logs a completion line for every run."""

    @override
    def setUp(self) -> None:
        self.queue = _FakeQueue()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.janitor = Janitor(  # pyright: ignore[reportUninitializedInstanceVariable]
            logger, self.queue, Lock(), Event(), online_tag_thread=None
        )

    def test_logs_zero_when_nothing_failed(self) -> None:
        """A no-op run still logs, so the admin button never runs silently."""
        with _capture_logs() as logs:
            self.janitor.force_update_all_failed_imports()
        assert any("Force update queued for 0 failed imports" in line for line in logs)
        assert not self.queue.items

    def test_logs_total_and_queues_imports(self) -> None:
        """Queued failed imports are counted in the completion log."""
        library = Library.objects.create(path="/lib-failed-imports")
        # bulk_create skips WatchedPath.presave(), which would stat() the path.
        FailedImport.objects.bulk_create(
            [
                FailedImport(library=library, path="/lib-failed-imports/a.cbz"),
                FailedImport(library=library, path="/lib-failed-imports/b.cbz"),
            ]
        )
        with _capture_logs() as logs:
            self.janitor.force_update_all_failed_imports()
        assert any("Force update queued for 2 failed imports" in line for line in logs)
        assert len(self.queue.items) == 1
        assert isinstance(self.queue.items[0], ImportTask)
