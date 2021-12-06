"""Library process worker for background tasks."""
from logging import getLogger
from multiprocessing import Process

from codex.librarian.covers.coverd import CoverCreator
from codex.librarian.db.updaterd import Updater
from codex.librarian.janitor.crond import Crond, janitor
from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    ComicCoverTask,
    JanitorTask,
    NotifierTask,
    PollLibrariesTask,
    UpdaterTask,
    WatchdogEventTask,
    WatchdogSyncTask,
)
from codex.librarian.watchdog.eventsd import EventBatcher
from codex.librarian.watchdog.observers import (
    LibraryEventObserver,
    LibraryPollingObserver,
)
from codex.notifier import Notifier


LOG = getLogger(__name__)


class LibrarianDaemon(Process):
    """Librarian Process."""

    SHUTDOWN_TIMEOUT = 5
    MAX_WS_ATTEMPTS = 5
    SHUTDOWN_TASK = "shutdown"
    proc = None

    def __init__(self):
        """Create threads and process pool."""
        super().__init__(name="librarian", daemon=False)

    def _process_task(self, task):
        """Process an individual task popped off the queue."""
        run = True
        try:
            if isinstance(task, ComicCoverTask):
                self.cover_creator.queue.put(task)
            elif isinstance(task, WatchdogEventTask):
                self.event_batcher.queue.put(task)
            elif isinstance(task, UpdaterTask):
                self.updater.queue.put(task)
            elif isinstance(task, NotifierTask):
                Notifier.thread.queue.put(task)
            elif isinstance(task, WatchdogSyncTask):
                for observer in self._observers:
                    observer.sync_library_watches()
            elif isinstance(task, PollLibrariesTask):
                self.library_polling_observer.poll(task.library_ids, task.force)
            elif isinstance(task, JanitorTask):
                janitor(task)
            elif task == self.SHUTDOWN_TASK:
                LOG.verbose("Shutting down Librarian...")  # type: ignore
                run = False
            else:
                LOG.warning(f"Unhandled Librarian task: {task}")
        except Exception as exc:
            LOG.exception(exc)
        return run

    def _create_threads(self):
        """Create all the threads."""
        self.cover_creator = CoverCreator()
        self.updater = Updater()
        self.event_batcher = EventBatcher()
        self.file_system_event_observer = LibraryEventObserver()
        self.library_polling_observer = LibraryPollingObserver()
        self.crond = Crond()
        self._threads = (
            self.cover_creator,
            self.updater,
            self.event_batcher,
            self.file_system_event_observer,
            self.library_polling_observer,
            self.crond,
        )
        self._observers = (
            self.file_system_event_observer,
            self.library_polling_observer,
        )

    def _start_threads(self):
        """Start all librarian's threads."""
        LOG.debug("Starting Librarian threads.")
        for thread in self._threads:
            thread.start()
        LOG.debug("Started Librarian threads.")

    def _stop_threads(self):
        """Stop all librarian's threads."""
        LOG.debug("Stopping Librarain threads...")
        for thread in reversed(self._threads):
            thread.stop()
        LOG.debug("Stopped Librarian threads.")

    def run(self):
        """
        Process tasks from the queue.

        This process also runs the crond thread and the Watchdog Observer
        threads.
        """
        try:
            LOG.verbose("Started Librarian process.")  # type: ignore
            self._create_threads()
            self._start_threads()
            run = True
            LOG.verbose(  # type: ignore
                "Librarian started threads and waiting for tasks."
            )
            while run:
                task = LIBRARIAN_QUEUE.get()
                run = self._process_task(task)
            self._stop_threads()
        except Exception as exc:
            LOG.error("Librarian crashed.")
            LOG.exception(exc)
        LOG.verbose("Stopped Librarian process.")  # type: ignore

    @classmethod
    def startup(cls):
        """Create a new librarian daemon and run it."""
        cls.proc = LibrarianDaemon()
        cls.proc.start()
        LIBRARIAN_QUEUE.put(WatchdogSyncTask())

    @classmethod
    def shutdown(cls):
        """Stop the librarian process."""
        LIBRARIAN_QUEUE.put(cls.SHUTDOWN_TASK)
        if cls.proc:
            LOG.debug("Waiting to shut down librarian...")
            cls.proc.join()
