"""Library process worker for background tasks."""
from logging import getLogger
from multiprocessing import Process

from codex.librarian.coverd import CoverCreator
from codex.librarian.crond import Crond
from codex.librarian.db.updaterd import Updater
from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    ComicCoverTask,
    DBDiffTask,
    NotifierTask,
    PollLibrariesTask,
    RestartTask,
    UpdateCronTask,
    VacuumCronTask,
    WatchdogTask,
)
from codex.librarian.update import restart_codex, update_codex
from codex.librarian.vacuum import vacuum_db
from codex.librarian.watchdog.eventsd import EventBatcher
from codex.librarian.watchdog.observers import (
    LibraryEventObserver,
    LibraryPollingObserver,
)
from codex.models import Comic, Folder
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

    def process_task(self, task):
        """Process an individual task popped off the queue."""
        run = True
        try:
            if isinstance(task, ComicCoverTask):
                self.cover_creator.queue.put(task)
            elif isinstance(task, DBDiffTask):
                self.updater.queue.put(task)
            elif isinstance(task, NotifierTask):
                Notifier.thread.queue.put(task)
            elif isinstance(task, WatchdogTask):
                self.file_system_event_observer.sync_library_watches()
                self.library_polling_observer.sync_library_watches()
            elif isinstance(task, UpdateCronTask):
                update_codex(task.force)
            elif isinstance(task, PollLibrariesTask):
                self.library_polling_observer.poll(task.library_ids, task.force)
            elif isinstance(task, RestartTask):
                restart_codex()
            elif isinstance(task, VacuumCronTask):
                vacuum_db()
            elif task == self.SHUTDOWN_TASK:
                LOG.verbose("Shutting down Librarian...")  # type: ignore
                run = False
            else:
                LOG.warning(f"Unhandled Librarian task: {task}")
        except (Comic.DoesNotExist, Folder.DoesNotExist) as exc:
            LOG.warning(exc)
        except Exception as exc:
            LOG.exception(exc)
        return run

    def start_threads(self):
        """Start all librarian's threads."""
        LOG.debug("Creating Librarian threads...")
        self.cover_creator = CoverCreator()
        self.updater = Updater()
        self.file_system_event_observer = LibraryEventObserver()
        self.library_polling_observer = LibraryPollingObserver()
        self.crond = Crond()
        LOG.debug("Created Librarian threads.")
        LOG.debug("Starting Librarian threads.")
        EventBatcher.startup()
        self.cover_creator.start()
        self.updater.start()
        self.file_system_event_observer.start()
        self.library_polling_observer.start()
        self.crond.start()
        LOG.debug("Started Librarian threads.")

    def stop_threads(self):
        """Stop all librarian's threads."""
        LOG.debug("Stopping Librarain threads...")
        self.crond.stop()
        self.file_system_event_observer.stop()
        self.library_polling_observer.stop()
        self.updater.stop()
        EventBatcher.thread.stop()
        self.cover_creator.stop()
        LOG.debug("Stopped Librarian threads.")
        LOG.debug("Joining Librarian threads.")
        self.crond.join()
        self.file_system_event_observer.join()
        self.library_polling_observer.join()
        self.updater.join()
        EventBatcher.thread.join()
        self.cover_creator.join()
        LOG.debug("Joined Librarian threads.")

    def run(self):
        """
        Process tasks from the queue.

        This proces also runs the crond thread and the Watchdog Observer
        threads.
        """
        try:
            LOG.verbose("Started Librarian process.")  # type: ignore
            self.start_threads()
            run = True
            LOG.verbose(  # type: ignore
                "Librarian started threads and waiting for tasks."
            )
            while run:
                task = LIBRARIAN_QUEUE.get()
                run = self.process_task(task)
            self.stop_threads()
        except Exception as exc:
            LOG.error("Librarian crashed.")
            LOG.exception(exc)
        LOG.verbose("Stopped Librarian process.")  # type: ignore

    @classmethod
    def startup(cls):
        """Create a new librarian daemon and run it."""
        cls.proc = LibrarianDaemon()
        cls.proc.start()
        LIBRARIAN_QUEUE.put(WatchdogTask())

    @classmethod
    def shutdown(cls):
        """Stop the librarian process."""
        LIBRARIAN_QUEUE.put(cls.SHUTDOWN_TASK)
        if cls.proc:
            LOG.debug("Waiting to shut down librarian...")
            cls.proc.join()
