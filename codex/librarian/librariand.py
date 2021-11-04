"""Library process worker for background tasks."""
from logging import getLogger
from multiprocessing import Process
from time import sleep

from codex.librarian.cover import CoverCreator
from codex.librarian.crond import Crond
from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    ComicCoverCreateTask,
    NotifierTask,
    RestartTask,
    ScannerTask,
    UpdateCronTask,
    VacuumCronTask,
    WatcherCronTask,
)
from codex.librarian.scanner import Scanner
from codex.librarian.update import restart_codex, update_codex
from codex.librarian.vacuum import vacuum_db
from codex.librarian.watcherd import Uatu
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
        LOG.debug("Librarian initialized.")

    def process_task(self, task):
        """Process an individual task popped off the queue."""
        run = True
        try:
            if task and hasattr(task, "sleep"):
                sleep(task.sleep)

            if isinstance(task, ComicCoverCreateTask):
                self.cover_creator.queue.put(task)
            elif isinstance(task, ScannerTask):
                self.scanner.queue.put(task)
            elif isinstance(task, NotifierTask):
                Notifier.thread.queue.put(task)
            elif isinstance(task, WatcherCronTask):
                self.watcher.set_all_library_watches()
            elif isinstance(task, UpdateCronTask):
                update_codex(task.force)
            elif isinstance(task, RestartTask):
                restart_codex()
            elif isinstance(task, VacuumCronTask):
                vacuum_db()
            elif task == self.SHUTDOWN_TASK:
                LOG.info("Shutting down Librarian...")
                run = False
            else:
                LOG.warning(f"Unhandled task popped: {task}")
        except (Comic.DoesNotExist, Folder.DoesNotExist) as exc:
            LOG.warning(exc)
        except Exception as exc:
            LOG.exception(exc)
        return run

    def start_threads(self):
        """Start all librarian's threads."""
        self.cover_creator = CoverCreator()
        self.scanner = Scanner()
        self.watcher = Uatu()
        self.crond = Crond()
        LOG.debug("Created Threads.")
        self.cover_creator.start()
        self.scanner.start()
        self.watcher.start()
        self.crond.start()
        LOG.debug("Started Threads.")

    def stop_threads(self):
        """Stop all librarian's threads."""
        LOG.debug("Joining threads...")
        self.crond.join()
        self.watcher.stop()
        self.watcher.join()
        self.scanner.join()
        self.cover_creator.join()
        LOG.debug("Stopped threads.")

    def run(self):
        """
        Process tasks from the queue.

        This proces also runs the crond thread and the Watchdog Observer
        threads.
        """
        try:
            LOG.debug("Started Librarian.")
            self.start_threads()
            run = True
            LOG.info("Librarian started threads and waiting for tasks.")
            while run:
                task = LIBRARIAN_QUEUE.get()
                run = self.process_task(task)
            self.stop_threads()
        except Exception as exc:
            LOG.error("Librarian crashed.")
            LOG.exception(exc)
        LOG.info("Stopped Librarian.")

    @classmethod
    def startup(cls):
        """Create a new librarian daemon and run it."""
        cls.proc = LibrarianDaemon()
        cls.proc.start()

    @classmethod
    def shutdown(cls):
        """Stop the librarian process."""
        LIBRARIAN_QUEUE.put(cls.SHUTDOWN_TASK)
        if cls.proc:
            LOG.debug("Waiting to shut down librarian...")
            cls.proc.join()
