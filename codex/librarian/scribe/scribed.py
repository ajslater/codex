"""Bulk import and move comics and folders."""

from multiprocessing import Manager
from queue import PriorityQueue

from typing_extensions import override

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
from codex.librarian.scribe.tasks import (
    ImportAbortTask,
    LazyImportComicsTask,
    SearchIndexSyncAbortTask,
    UpdateGroupsTask,
)
from codex.librarian.scribe.timestamp_update import TimestampUpdater
from codex.librarian.threads import QueuedThread

ABORT_SEARCH_UPDATE_TASKS = (
    SearchIndexClearTask,
    SearchIndexSyncAbortTask,
    JanitorFTSRebuildTask,
)


class ScribeThread(QueuedThread):
    """A worker to handle all bulk database updates."""

    SHUTDOWN_MSG = (0, QueuedThread.SHUTDOWN_MSG)

    def __init__(self, *args, **kwargs):
        """Initialize abort event."""
        self.abort_import_event = Manager().Event()
        self.abort_search_update_event = Manager().Event()
        self.abort_cleanup_event = Manager().Event()
        super().__init__(*args, queue=PriorityQueue(), **kwargs)

    @override
    def process_item(self, item):
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
            case UpdateGroupsTask():
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
                )
                worker.handle_task(task)
            case _:
                self.log.warning(f"Bad task sent to scribe: {task}")

    def put(self, task):
        """Put item in queue, and signal events."""
        if isinstance(task, ABORT_SEARCH_UPDATE_TASKS):
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
        priority = get_task_priority(task)
        item = (priority, task)
        self.queue.put(item)
