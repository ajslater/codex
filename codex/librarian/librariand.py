"""Library process worker for background tasks."""
import threading

from multiprocessing import Process
from time import sleep

from codex.darwin_mp import force_darwin_multiprocessing_fork
from codex.librarian.covers.coverd import CoverCreator
from codex.librarian.covers.tasks import CoverTask
from codex.librarian.db.tasks import UpdaterTask
from codex.librarian.db.updaterd import Updater
from codex.librarian.janitor.crond import Crond, janitor
from codex.librarian.janitor.tasks import JanitorTask
from codex.librarian.queue_mp import LIBRARIAN_QUEUE, DelayedTasks
from codex.librarian.search.searchd import SearchIndexer
from codex.librarian.search.tasks import (
    SearchIndexerTask,
    SearchIndexRebuildIfDBChangedTask,
)
from codex.librarian.status_control import StatusControl, StatusControlFinishTask
from codex.librarian.watchdog.eventsd import EventBatcher
from codex.librarian.watchdog.observers import (
    LibraryEventObserver,
    LibraryPollingObserver,
)
from codex.librarian.watchdog.tasks import (
    WatchdogEventTask,
    WatchdogPollLibrariesTask,
    WatchdogSyncTask,
)
from codex.notifier.notifierd import Notifier
from codex.notifier.tasks import NotifierTask
from codex.settings.logging import get_logger
from codex.threads import QueuedThread


LOG = get_logger(__name__)


class DelayedTasksThread(QueuedThread):
    """Wait for the DB to sync before running tasks."""

    NAME = "DelayedTask"  # type: ignore

    def process_item(self, item):
        """Sleep and then put tasks on the queue."""
        sleep(item.delay)
        for task in item.tasks:
            LIBRARIAN_QUEUE.put(task)


class LibrarianDaemon(Process):
    """Librarian Process."""

    NAME = "Librarian"
    SHUTDOWN_TIMEOUT = 5
    MAX_WS_ATTEMPTS = 5
    SHUTDOWN_TASK = "shutdown"
    proc = None

    def __init__(self):
        """Init process."""
        super().__init__(name=self.NAME, daemon=False)

    def _process_task(self, task):
        """Process an individual task popped off the queue."""
        run = True
        if isinstance(task, CoverTask):
            self.cover_creator.queue.put(task)
        elif isinstance(task, WatchdogEventTask):
            self.event_batcher.queue.put(task)
        elif isinstance(task, UpdaterTask):
            self.updater.queue.put(task)
        elif isinstance(task, NotifierTask) and Notifier.thread:
            Notifier.thread.queue.put(task)
        elif isinstance(task, WatchdogSyncTask):
            for observer in self._observers:
                observer.sync_library_watches()
        elif isinstance(task, WatchdogPollLibrariesTask):
            self.library_polling_observer.poll(task.library_ids, task.force)
        elif isinstance(task, SearchIndexerTask):
            self.search_indexer.queue.put(task)
        elif isinstance(task, JanitorTask):
            janitor(task)
        elif isinstance(task, StatusControlFinishTask):
            StatusControl.finish(task.type, task.notify)
        elif isinstance(task, DelayedTasks):
            self.delayed_tasks.queue.put(task)
        elif task == self.SHUTDOWN_TASK:
            LOG.verbose("Shutting down Librarian...")
            run = False
        else:
            LOG.warning(f"Unhandled Librarian task: {task}")
        return run

    def _create_threads(self):
        """Create all the threads."""
        LOG.debug("Creating Librarian threads...")
        force_darwin_multiprocessing_fork()
        LOG.debug(f"Active threads before thread creation: {threading.active_count()}")
        self.delayed_tasks = DelayedTasksThread()
        LOG.debug("Created DelayedTasksThread")
        self.cover_creator = CoverCreator()
        LOG.debug("Created CoverCreatorThread")
        self.search_indexer = SearchIndexer()
        LOG.debug("Created SearchIndexerThread")
        self.updater = Updater()
        LOG.debug("Created UpdaterThread")
        self.event_batcher = EventBatcher()
        LOG.debug("Created EventBatcherThread")
        self.file_system_event_observer = LibraryEventObserver()
        LOG.debug("Created FSEOThread")
        self.library_polling_observer = LibraryPollingObserver()
        LOG.debug("Created PollingObserverThread")
        self.crond = Crond()
        LOG.debug("Created CrondThread")
        self._threads = (
            self.delayed_tasks,
            self.cover_creator,
            self.search_indexer,
            self.updater,
            self.event_batcher,
            self.file_system_event_observer,
            self.library_polling_observer,
            self.crond,
        )
        LOG.debug("Created _threads tuple")
        self._observers = (
            self.file_system_event_observer,
            self.library_polling_observer,
        )
        LOG.debug("Threads created")

    def _start_threads(self):
        """Start all librarian's threads."""
        LOG.debug(f"Starting all {self.NAME} threads.")
        for thread in self._threads:
            thread.start()
        LOG.debug(f"Started all {self.NAME} threads.")

    def _stop_threads(self):
        """Stop all librarian's threads."""
        LOG.debug(f"Stopping all {self.NAME} threads...")
        for thread in reversed(self._threads):
            thread.stop()
        for thread in reversed(self._threads):
            thread.join()
        LOG.debug(f"Stopped all {self.NAME} threads.")

    def run(self):
        """
        Process tasks from the queue.

        This process also runs the crond thread and the Watchdog Observer
        threads.
        """
        try:
            LOG.verbose("Started Librarian process.")
            self._create_threads()
            LOG.debug("Created Librarian Threads, Starting.")
            self._start_threads()
            task = SearchIndexRebuildIfDBChangedTask()
            LIBRARIAN_QUEUE.put(task)
            run = True
            LOG.verbose("Librarian started threads and waiting for tasks.")
            while run:
                try:
                    task = LIBRARIAN_QUEUE.get()
                    run = self._process_task(task)
                except Exception as exc:
                    LOG.error(f"Error in {self.NAME}")
                    LOG.exception(exc)
            self._stop_threads()
        except Exception as exc:
            LOG.error("Librarian crashed.")
            LOG.exception(exc)
        LOG.verbose("Stopped Librarian process.")

    @classmethod
    def startup(cls):
        """Create a new librarian daemon and run it."""
        cls.proc = LibrarianDaemon()
        cls.proc.start()
        LIBRARIAN_QUEUE.put(WatchdogSyncTask())

    @classmethod
    def shutdown(cls):
        """Stop the librarian process."""
        if not cls.proc:
            LOG.warning(f"Cannot shutdown {cls.NAME}. It hasn't started.")
            return
        LIBRARIAN_QUEUE.put(cls.SHUTDOWN_TASK)
        LOG.debug(f"Waiting for {cls.NAME} to join...")
        cls.proc.join()
        cls.proc = None
        LOG.debug(f"{cls.NAME} joined.")
