"""
An upgrade's arc lists are synced at startup, not hours later (B2).

Migration 0061 writes each tags source with a blank revision, so the
first tags sync rebuilds every arc list, and until it runs an edit made
to one can be lost. That sync was the nightly one. The librarian now
queues it when it starts, if any tags source is still unstamped.
"""

from codex.librarian.librariand import queue_unstamped_tags_sync
from codex.librarian.scribe.janitor.tasks import JanitorSyncReadingListsTask
from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.models import ReadingListSource
from codex.models.readinglist import ReadingListSourceKind
from tests.test_reading_lists import ReadingListFixture


class _Queue:
    def __init__(self) -> None:
        self.items: list = []

    def put(self, item) -> None:
        self.items.append(item)


def _queued() -> list:
    queue = _Queue()
    queue_unstamped_tags_sync(queue)
    return queue.items


class StartupTagsSyncTests(ReadingListFixture):
    """Arc lists as the migration leaves them, and after a sync."""

    def test_a_blank_revision_queues_the_sync(self) -> None:
        self.tag(self.comics[0], "Civil War", 1)
        sync_tag_lists()
        ReadingListSource.objects.filter(kind=ReadingListSourceKind.TAGS).update(
            revision=""
        )
        (task,) = _queued()
        assert isinstance(task, JanitorSyncReadingListsTask)

    def test_no_tags_source_queues_nothing(self) -> None:
        assert _queued() == []

    def test_a_synced_install_queues_nothing(self) -> None:
        """The sync stamps the revisions, so the next start is quiet."""
        self.tag(self.comics[0], "Civil War", 1)
        ReadingListSource.objects.filter(kind=ReadingListSourceKind.TAGS).update(
            revision=""
        )
        sync_tag_lists()
        assert _queued() == []
