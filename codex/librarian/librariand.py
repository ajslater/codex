"""Library process worker for background tasks."""
import logging
import platform

from multiprocessing import Pool, Process
from time import sleep

from codex.librarian.cover import create_comic_cover
from codex.librarian.crond import Crond
from codex.librarian.queue_mp import (
    QUEUE,
    BulkComicMovedTask,
    BulkFolderMovedTask,
    ComicCoverCreateTask,
    LibraryChangedTask,
    RestartTask,
    ScanDoneTask,
    ScannerCronTask,
    ScanRootTask,
    UpdateCronTask,
    VacuumCronTask,
    WatcherCronTask,
)
from codex.librarian.scanner import Scanner
from codex.librarian.update import restart_codex, update_codex
from codex.librarian.vacuum import vacuum_db
from codex.librarian.watcherd import Uatu
from codex.models import Comic, Folder
from codex.serializers.webpack import (
    WEBSOCKET_MESSAGES as WS_MSGS,  # TODO Replace with tasks
)
from codex.settings.django_setup import django_setup
from codex.websocket_server import NOTIFIER, NotifierMessage


django_setup()  # XXX can I move this to run()?

LOG = logging.getLogger(__name__)
if platform.system() == "Darwin":
    # XXX Fixes QUEUE sharing with default spawn start method. The spawn
    # method is also very very slow. Use fork and the
    # OBJC_DISABLE_INITIALIZE_FORK_SAFETY environment variable for macOS.
    # https://bugs.python.org/issue40106
    from multiprocessing import set_start_method

    set_start_method("fork", force=True)


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

    @staticmethod
    def _notify(type, msg):
        """Send the message to the notifier queue."""
        message = NotifierMessage(type, WS_MSGS[msg])
        NOTIFIER.queue.put(message)

    def process_task(self, task):
        """Process an individual task popped off the queue."""
        run = True
        try:
            print(task)
            if task and hasattr(task, "sleep"):
                sleep(task.sleep)

            if isinstance(task, ComicCoverCreateTask):
                # Cover creation is cpu bound, farm it out.
                args = (task.src_path, task.db_cover_path, task.force)
                self.pool.apply_async(create_comic_cover, args=args)
            elif isinstance(
                task,
                (
                    ScanRootTask,
                    BulkFolderMovedTask,
                    BulkComicMovedTask,
                    ScannerCronTask,
                ),
            ):
                self._notify(NotifierMessage.ADMIN_BROADCAST, "SCAN_LIBRARY")
                self.scanner.queue.put(task)
            elif isinstance(task, ScanDoneTask):
                if task.failed_imports:
                    msg = "FAILED_IMPORTS"
                else:
                    msg = "SCAN_DONE"
                self._notify(NotifierMessage.ADMIN_BROADCAST, msg)
            elif isinstance(task, LibraryChangedTask):
                self._notify(NotifierMessage.BROADCAST, "LIBRARY_CHANGED")
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
        self.scanner = Scanner()
        self.watcher = Uatu()
        self.crond = Crond()
        self.pool = Pool()
        LOG.debug("Created Threads.")
        self.scanner.start()
        self.watcher.start()
        self.crond.start()
        LOG.debug("Started Threads.")

    def stop_threads(self):
        """Stop all librarian's threads."""
        LOG.debug("Stopping threads & pool...")
        self.pool.close()
        self.watcher.stop()
        LOG.debug("Joining threads & pool...")
        self.crond.join()
        self.watcher.join()
        self.pool.join()
        self.scanner.join()
        LOG.debug("Stopped threads & pool.")

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
                task = QUEUE.get()
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
        global QUEUE
        QUEUE.put(LibrarianDaemon.SHUTDOWN_TASK)
        if cls.proc:
            LOG.debug("Waiting to shut down...")
            cls.proc.join()
