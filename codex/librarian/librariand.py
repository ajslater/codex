"""Library process worker for background tasks."""
import logging
import platform

from multiprocessing import Pool, Process
from time import sleep

import simplejson as json

from websocket import create_connection

from codex.librarian.cover import create_comic_cover
from codex.librarian.crond import Crond
from codex.librarian.importer import import_comic, obj_deleted, obj_moved
from codex.librarian.queue import (
    QUEUE,
    ComicCoverCreateTask,
    ComicDeletedTask,
    ComicModifiedTask,
    ComicMovedTask,
    FolderDeletedTask,
    FolderMovedTask,
    LibraryChangedTask,
    RestartTask,
    ScanDoneTask,
    ScannerCronTask,
    ScanRootTask,
    UpdateCronTask,
    VacuumCronTask,
    WatcherCronTask,
)
from codex.librarian.scanner import scan_cron, scan_root
from codex.librarian.update import restart_codex, update_codex
from codex.librarian.vacuum import vacuum_db
from codex.librarian.watcherd import Uatu
from codex.models import Comic, Folder
from codex.serializers.webpack import WEBSOCKET_MESSAGES as WS_MSGS
from codex.settings.django_setup import django_setup
from codex.settings.settings import PORT
from codex.websocket_server import BROADCAST_SECRET, IPC_URL_TMPL, MessageType


django_setup()

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
        LOG.debug("Librarian initializing...")
        super().__init__(name="librarian", daemon=False)
        self.ws = None
        self.ipc_url = IPC_URL_TMPL.format(port=PORT)
        LOG.debug("Librarian initialized.")

    def ensure_websocket(self):
        """Connect to the websocket broadcast url."""
        # Its easier to inject these into the ws server event loop
        # by sending them instead of using shared memory.
        if self.ws and self.ws.connected:
            LOG.debug(f"websocket already connected: {self.ws.connected}")
            return
        try:
            self.ws = create_connection(self.ipc_url)
            LOG.debug("connected to websocket server")
        except ConnectionRefusedError:
            LOG.debug("connection to websocket server refused.")

    def send_json(self, typ, message):
        """Send a JSON message."""
        self.ensure_websocket()
        if not self.ws or not self.ws.connected:
            return False
        obj = {"type": typ}
        if typ in MessageType.SECRET_TYPES:
            obj["secret"] = BROADCAST_SECRET.value
        obj["message"] = message
        msg = json.dumps(obj)
        self.ws.send(msg)
        return True

    def process_task(self, task):
        """Process an individual task popped off the queue."""
        run = True
        try:
            if task and hasattr(task, "sleep"):
                sleep(task.sleep)
            if isinstance(task, ScanRootTask):
                msg = WS_MSGS["SCAN_LIBRARY"]
                self.send_json(MessageType.ADMIN_BROADCAST, msg)
                # no retry
                scan_root(task.library_id, task.force)
            elif isinstance(task, ScanDoneTask):
                if task.failed_imports:
                    msg = WS_MSGS["FAILED_IMPORTS"]
                else:
                    msg = WS_MSGS["SCAN_DONE"]
                if not self.send_json(MessageType.ADMIN_BROADCAST, msg):
                    QUEUE.put(task)
            elif isinstance(task, ComicModifiedTask):
                import_comic(task.library_id, task.src_path)
            elif isinstance(task, ComicCoverCreateTask):
                # Cover creation is cpu bound, farm it out.
                args = (task.src_path, task.db_cover_path, task.force)
                self.pool.apply_async(create_comic_cover, args=args)
            elif isinstance(task, FolderMovedTask):
                obj_moved(task.src_path, task.dest_path, Folder)
            elif isinstance(task, ComicMovedTask):
                obj_moved(task.src_path, task.dest_path, Comic)
            elif isinstance(task, ComicDeletedTask):
                obj_deleted(task.src_path, Comic)
            elif isinstance(task, FolderDeletedTask):
                obj_deleted(task.src_path, Folder)
            elif isinstance(task, LibraryChangedTask):
                msg = WS_MSGS["LIBRARY_CHANGED"]
                if not self.send_json(MessageType.BROADCAST, msg):
                    QUEUE.put(task)
            elif isinstance(task, WatcherCronTask):
                self.watcher.set_all_library_watches()
            elif isinstance(task, ScannerCronTask):
                scan_cron()
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
        self.watcher = Uatu()
        self.crond = Crond()
        self.pool = Pool()
        LOG.debug("Created Threads.")
        self.watcher.start()
        self.crond.start()
        LOG.debug("Started Threads.")

    def stop_threads(self):
        """Stop all librarian's threads."""
        LOG.debug("Stopping threads & pool...")
        if self.ws:
            self.ws.close()
        self.crond.stop()
        self.pool.close()
        self.watcher.stop()
        LOG.debug("Joining threads & pool...")
        self.crond.join()
        self.watcher.join()
        self.pool.join()
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
