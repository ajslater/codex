"""Bulk import and move comics and folders."""

from multiprocessing import Manager
from queue import PriorityQueue
from typing import TYPE_CHECKING, Final, override

from codex.librarian.scribe.force_updater import ForceUpdater
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.janitor.adopt_folders import OrphanFolderAdopter
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.librarian.scribe.janitor.tasks import (
    JanitorAdoptOrphanFoldersTask,
    JanitorFTSRebuildTask,
    JanitorTask,
)
from codex.librarian.scribe.lazy_importer import LazyImporter
from codex.librarian.scribe.priority import get_task_priority
from codex.librarian.scribe.search.handler import SearchIndexer
from codex.librarian.scribe.search.tasks import (
    SearchIndexClearTask,
    SearchIndexerTask,
)
from codex.librarian.scribe.tag_writer import TagWriter
from codex.librarian.scribe.tasks import (
    BulkTagWriteTask,
    CleanupAbortTask,
    ForceUpdateComicsTask,
    ImportAbortTask,
    LazyImportComicsTask,
    SearchIndexSyncAbortTask,
    TagWriteAbortTask,
    UpdateCollectionsTask,
)
from codex.librarian.scribe.timestamp_update import TimestampUpdater
from codex.librarian.threads import QueuedThread

if TYPE_CHECKING:
    from codex.librarian.onlinetag.onlinetagd import OnlineTagThread

_ABORT_SEARCH_UPDATE_TASKS: Final = (
    SearchIndexClearTask,
    SearchIndexSyncAbortTask,
    JanitorFTSRebuildTask,
)


class ScribeThread(QueuedThread):
    """A worker to handle all bulk database updates."""

    SHUTDOWN_MSG = (0, QueuedThread.SHUTDOWN_MSG)
    # Importer / janitor / search bursts are minutes-to-hours apart on
    # a typical install. Releasing the conn between bursts saves an
    # open file handle + ~50 KiB pinned for the entire idle gap; the
    # ~5-20 ms reopen cost on the next task is invisible against the
    # work that follows.
    CLOSE_DB_BETWEEN_TASKS = True

    # Set by ``LibrarianDaemon._create_threads`` after both threads
    # exist so ``Janitor.cleanup_tagging_state`` can ask the
    # OnlineTagThread whether a persisted session is still live.
    online_tag_thread: "OnlineTagThread | None" = None

    def __init__(self, *args, **kwargs) -> None:
        """Initialize abort event."""
        self.abort_import_event = Manager().Event()
        self.abort_search_update_event = Manager().Event()
        self.abort_cleanup_event = Manager().Event()
        self.abort_tag_write_event = Manager().Event()
        super().__init__(*args, queue=PriorityQueue(), **kwargs)

    @override
    def process_item(self, item) -> None:
        """Run the updater."""
        task = item[-1]
        match task:
            case ImportTask():
                importer = ComicImporter(
                    task,
                    self.log,
                    self.librarian_queue,
                    self.db_write_lock,
                    self.abort_import_event,
                )
                importer.apply()
            case LazyImportComicsTask():
                worker = LazyImporter(
                    self.log, self.librarian_queue, self.db_write_lock
                )
                worker.lazy_import(task)
            case ForceUpdateComicsTask():
                worker = ForceUpdater(
                    self.log, self.librarian_queue, self.db_write_lock
                )
                worker.force_update(task)
            case UpdateCollectionsTask():
                worker = TimestampUpdater(
                    self.log, self.librarian_queue, self.db_write_lock
                )
                worker.update_groups(task)
            case JanitorAdoptOrphanFoldersTask():
                worker = OrphanFolderAdopter(
                    self.log,
                    self.librarian_queue,
                    self.db_write_lock,
                    event=self.abort_import_event,
                )
                worker.adopt_orphan_folders()
            case SearchIndexerTask():
                worker = SearchIndexer(
                    self.log,
                    self.librarian_queue,
                    self.db_write_lock,
                    event=self.abort_search_update_event,
                )
                worker.handle_task(task)
            case JanitorTask():
                worker = Janitor(
                    self.log,
                    self.librarian_queue,
                    self.db_write_lock,
                    event=self.abort_cleanup_event,
                    online_tag_thread=self.online_tag_thread,
                )
                worker.handle_task(task)
            case BulkTagWriteTask():
                worker = TagWriter(
                    self.log,
                    self.librarian_queue,
                    self.db_write_lock,
                    event=self.abort_tag_write_event,
                )
                worker.write_tags(task)
            case _:
                self.log.warning(f"Bad task sent to scribe: {task}")

    def put(self, task) -> None:
        """Put item in queue, and signal events."""
        if isinstance(task, _ABORT_SEARCH_UPDATE_TASKS):
            self.abort_search_update_event.set()
            if isinstance(task, ImportTask | JanitorAdoptOrphanFoldersTask):
                self.abort_cleanup_event.set()
                self.log.debug("Abort cleanup db signal given.")
            elif isinstance(task, SearchIndexSyncAbortTask):
                self.log.debug(
                    "Search Index Sync abort signal given. It may take a while for the current import chunk to finish."
                )
                return
        elif isinstance(task, ImportAbortTask):
            self.abort_import_event.set()
            self.log.debug("Import abort signal given.")
            return
        elif isinstance(task, TagWriteAbortTask):
            self.abort_tag_write_event.set()
            self.log.debug("Tag write abort signal given.")
            return
        elif isinstance(task, CleanupAbortTask):
            self.abort_cleanup_event.set()
            self.log.debug("Cleanup abort signal given.")
            return
        priority = get_task_priority(task)
        item = (priority, task)
        self.queue.put(item)
