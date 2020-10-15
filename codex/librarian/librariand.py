"""Library process worker for background tasks."""
import logging
import os
import platform
import time

from multiprocessing import Pool
from multiprocessing import Process
from time import sleep

import simplejson as json

from websocket import create_connection

from codex.librarian.cover import create_comic_cover
from codex.librarian.crond import Crond
from codex.librarian.importer import import_comic
from codex.librarian.importer import obj_deleted
from codex.librarian.importer import obj_moved
from codex.librarian.queue import QUEUE
from codex.librarian.queue import ComicCoverCreateTask
from codex.librarian.queue import ComicDeletedTask
from codex.librarian.queue import ComicModifiedTask
from codex.librarian.queue import ComicMovedTask
from codex.librarian.queue import FolderDeletedTask
from codex.librarian.queue import FolderMovedTask
from codex.librarian.queue import LibraryChangedTask
from codex.librarian.queue import RestartTask
from codex.librarian.queue import ScanDoneTask
from codex.librarian.queue import ScannerCronTask
from codex.librarian.queue import ScanRootTask
from codex.librarian.queue import UpdateCronTask
from codex.librarian.queue import WatcherCronTask
from codex.librarian.scanner import scan_cron
from codex.librarian.scanner import scan_root
from codex.librarian.update import restart_codex
from codex.librarian.update import update_codex
from codex.librarian.watcherd import Uatu
from codex.models import Comic
from codex.models import Folder
from codex.serializers.webpack import WEBSOCKET_MESSAGES as WS_MSGS
from codex.settings.django_setup import django_setup
from codex.settings.settings import PORT
from codex.websocket_server import BROADCAST_SECRET
from codex.websocket_server import IPC_SUFFIX
from codex.websocket_server import WS_API_PATH
from codex.websocket_server import MessageType


django_setup()

LOG = logging.getLogger(__name__)
BROADCAST_URL_TMPL = "ws://localhost:{port}/" + WS_API_PATH + IPC_SUFFIX
MAX_WS_ATTEMPTS = 4
SHUTDOWN_TASK = "shutdown"
if platform.system() == "Darwin":
    # XXX Fixes QUEUE sharing with default spawn start method. The spawn
    # method is also very very slow. Use fork and the
    # OBJC_DISABLE_INITIALIZE_FORK_SAFETY environment variable for macOS.
    # https://bugs.python.org/issue40106
    from multiprocessing import set_start_method

    set_start_method("fork", force=True)


# XXX Should this inherit from Process?
class LibrarianDaemon:
    """Librarian Process."""

    proc = None

    def __init__(self, main_pid):
        """Create threads and process pool."""
        LOG.debug("Librarian initializing...")
        self.main_pid = main_pid
        self.watcher = Uatu()
        self.crond = Crond()
        self.pool = Pool()
        self.ws = None
        LOG.debug("Librarian initialized.")

    def ensure_websocket(self):
        """Connect to the websocket broadcast url."""
        # Its easier to inject these into the ws server event loop
        # by sending them instead of using shared memory.
        if self.ws is not None and self.ws.connected:
            return
        attempts = 0
        while self.ws is None or not self.ws.connected and attempts <= MAX_WS_ATTEMPTS:
            time.sleep(0.5)
            try:
                broadcast_url = BROADCAST_URL_TMPL.format(port=PORT)
                self.ws = create_connection(broadcast_url)
            except ConnectionRefusedError:
                attempts += 1
        if self.ws and self.ws.connected:
            LOG.info("Librarian connected to websockets.")
        else:
            LOG.error("Librarian cannot connect to websockets.")

    def send_json(self, typ, message):
        """Send a JSON message."""
        obj = {"type": typ}
        if typ in MessageType.SECRET_TYPES:
            obj["secret"] = BROADCAST_SECRET.value
        obj["message"] = message
        msg = json.dumps(obj)
        self.ensure_websocket()
        self.ws.send(msg)

    def process_task(self, task):
        """Process an individual task popped off the queue."""
        run = True
        try:
            if isinstance(task, ScanRootTask):
                msg = WS_MSGS["SCAN_LIBRARY"]
                self.send_json(MessageType.ADMIN_BROADCAST, msg)
                scan_root(task.library_id, task.force)
            elif isinstance(task, ScanDoneTask):
                if task.failed_imports:
                    msg = WS_MSGS["FAILED_IMPORTS"]
                else:
                    msg = WS_MSGS["SCAN_DONE"]
                self.send_json(MessageType.ADMIN_BROADCAST, msg)
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
                self.send_json(MessageType.BROADCAST, msg)
            elif isinstance(task, WatcherCronTask):
                sleep(task.sleep)
                self.watcher.set_all_library_watches()
            elif isinstance(task, ScannerCronTask):
                sleep(task.sleep)
                scan_cron()
            elif isinstance(task, UpdateCronTask):
                sleep(task.sleep)
                update_codex(self.main_pid, task.force)
            elif isinstance(task, RestartTask):
                sleep(task.sleep)
                restart_codex(self.main_pid)
            elif task == SHUTDOWN_TASK:
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
        LOG.info("Starting Librarian Threads...")
        self.watcher.start()
        LOG.debug("started Uatu")
        self.crond.start()
        LOG.debug("started Cron")

    def stop_threads(self):
        """Stop all librarian's threads."""
        LOG.debug("Stopping threads...")
        if self.ws:
            self.ws.close()
        self.pool.close()
        self.crond.stop()
        self.watcher.stop()
        self.crond.join()
        self.watcher.join()
        self.pool.join()

    def loop(self):
        """
        Process tasks from the queue.

        This proces also runs the crond thread and the Watchdog Observer
        threads.
        """
        try:
            LOG.info("Started Librarian.")
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

    @staticmethod
    def worker(main_pid):
        """Create a new librarian daemon and run it."""
        daemon = LibrarianDaemon(main_pid)
        daemon.loop()

    @classmethod
    def start(cls):
        """Start the worker process."""
        args = (os.getpid(),)
        cls.proc = Process(target=cls.worker, name="librarian", args=args, daemon=False)
        cls.proc.start()

    @classmethod
    def stop(cls):
        """Stop the librarian process."""
        QUEUE.put(SHUTDOWN_TASK)
        if cls.proc:
            cls.proc.join()
