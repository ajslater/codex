"""Everyone hears that reading lists changed, including from the tag sync."""

from unittest.mock import MagicMock

from loguru import logger

from codex.librarian.notifier.tasks import READING_LISTS_CHANGED_TASK
from codex.librarian.scribe.importer.init import Counts
from codex.librarian.scribe.importer.readinglists import ReadingListsImporter
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.websockets.consumers import ChannelGroups
from tests.test_reading_list_fetch import _Queue
from tests.test_reading_lists import ReadingListFixture


def _with_queue(cls, **attrs):
    worker = cls.__new__(cls)
    queue = _Queue()
    worker.librarian_queue = queue
    worker.status_controller = MagicMock()
    worker.log = logger
    for name, value in attrs.items():
        setattr(worker, name, value)
    return worker, queue


class ReadingListsChangedTests(ReadingListFixture):
    """The notice carries no names, so it goes to every browser."""

    def test_the_notice_goes_to_everyone(self) -> None:
        """Drawers and menus of every user reload, not only admins'."""
        assert READING_LISTS_CHANGED_TASK.group == ChannelGroups.ALL

    def test_an_import_sync_that_changed_lists_notifies(self) -> None:
        """A new arc tag makes a list, and browsers hear of it."""
        self.tag(self.comics[0], "Civil War", 1)
        importer, queue = _with_queue(ReadingListsImporter, counts=Counts(tags=1))
        importer.sync_reading_lists()
        assert READING_LISTS_CHANGED_TASK in queue

    def test_a_sync_that_changed_nothing_is_quiet(self) -> None:
        """No list changed, no notice."""
        importer, queue = _with_queue(ReadingListsImporter, counts=Counts(tags=1))
        importer.sync_reading_lists()
        assert READING_LISTS_CHANGED_TASK not in queue

    def test_the_janitor_sync_notifies(self) -> None:
        """The nightly sync tells browsers too."""
        self.tag(self.comics[0], "Civil War", 1)
        janitor, queue = _with_queue(Janitor)
        janitor.sync_reading_lists()
        assert READING_LISTS_CHANGED_TASK in queue
