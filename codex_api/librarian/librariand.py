"""Library process worker for background tasks."""
import logging
import time

from multiprocessing import Process

import simplejson as json
import websocket

from codex_api.librarian.crond import Crond
from codex_api.librarian.importer import import_comic
from codex_api.librarian.importer import obj_deleted
from codex_api.librarian.importer import obj_moved
from codex_api.librarian.queue import QUEUE
from codex_api.librarian.queue import ComicDeletedTask
from codex_api.librarian.queue import ComicModifiedTask
from codex_api.librarian.queue import ComicMovedTask
from codex_api.librarian.queue import FolderDeletedTask
from codex_api.librarian.queue import FolderMovedTask
from codex_api.librarian.queue import LibraryChangedTask
from codex_api.librarian.queue import ScannerCronTask
from codex_api.librarian.queue import ScanRootTask
from codex_api.librarian.queue import WatcherCronTask
from codex_api.librarian.queue import WatchLibraryTask
from codex_api.librarian.scanner import scan_cron
from codex_api.librarian.scanner import scan_root
from codex_api.librarian.watcherd import Uatu
from codex_api.models import Comic
from codex_api.models import Folder
from codex_api.websocket import BROADCAST_MSG
from codex_api.websocket import BROADCAST_SECRET
from codex_api.websocket import UNSUBSCRIBE_MSG


# from django.utils.autoreload import file_changed


LOG = logging.getLogger(__name__)
PORT = 8000
BROADCAST_PATH = "broadcast"
BROADCAST_URL = f"ws://localhost:{PORT}/{BROADCAST_PATH}"
SHUTDOWN_MSG = "shutdown"
MAX_WS_ATTEMPTS = 4


def get_websocket():
    """Connect to the websocket broadcast url."""
    ws = None
    attempts = 0
    while ws is None or not ws.connected and attempts <= MAX_WS_ATTEMPTS:
        time.sleep(0.5)
        try:
            ws = websocket.create_connection(BROADCAST_URL)
        except ConnectionRefusedError:
            attempts += 1
    if ws and ws.connected:
        send_json(ws, UNSUBSCRIBE_MSG)
        LOG.info("Librarian connected to websockets.")
    else:
        LOG.error("Librarian cannot connect to websockets.")
    return ws


def send_json(ws, typ, message=None):
    """Send a JSON message."""
    obj = {"type": typ}
    if typ == BROADCAST_MSG:
        obj["secret"] = BROADCAST_SECRET.value
    if message:
        obj["message"] = message
    msg = json.dumps(obj)
    if ws is None or not ws.connected:
        ws = get_websocket()
    ws.send(msg)
    return ws


def librarian():
    """
    Triage and process tasks from the queue.

    This proces also runs the crond thread and the Watchdog Observer
    threads.
    """
    LOG.info("Started Librarian.")
    ws = None
    run = True
    watcher = Uatu()
    crond = Crond()
    watcher.start()
    crond.start()
    while run:
        task = QUEUE.get()
        try:
            if isinstance(task, ScanRootTask):
                scan_root(task.library_id, task.force)
            elif isinstance(task, ComicModifiedTask):
                import_comic(task.library_id, task.src_path)
                # TODO use a higher performance db?
                # import is cpu bound, so farm it out.
                # pool.apply_async(import_comic,
                # args=(task.library_id, task.src_path))
            elif isinstance(task, FolderMovedTask):
                obj_moved(task.src_path, task.dest_path, Folder)
            elif isinstance(task, ComicMovedTask):
                obj_moved(task.src_path, task.dest_path, Comic)
            elif isinstance(task, ComicDeletedTask):
                obj_deleted(task.src_path, Comic)
            elif isinstance(task, FolderDeletedTask):
                obj_deleted(task.src_path, Folder)
            elif isinstance(task, LibraryChangedTask):
                ws = send_json(ws, BROADCAST_MSG, "libraryChanged")
            elif isinstance(task, WatchLibraryTask):
                watcher.set_library_watch(task.library_pk, task.watch)
            elif isinstance(task, WatcherCronTask):
                watcher.set_all_library_watches()
            elif isinstance(task, ScannerCronTask):
                scan_cron()
            elif task == SHUTDOWN_MSG:
                run = False
            else:
                LOG.warning(f"Unhandled task popped: {task}")
        except (Comic.DoesNotExist, Folder.DoesNotExist) as exc:
            LOG.warning(exc)
        except Exception as exc:
            LOG.exception(exc)
    crond.stop()
    watcher.stop()
    crond.join()
    watcher.join()
    LOG.info("Stopped Librarian.")


def start_librarian():
    """Start the worker process."""
    global proc
    proc = Process(target=librarian, name="codex-librarian", daemon=True)
    proc.start()
    # this signal is thrown by runserver which i don't use anymore
    # file_changed.connect(stop_librarian)


def stop_librarian(*args, **kwargs):
    """Stop the librarian process."""
    QUEUE.put(SHUTDOWN_MSG)
    proc.join()
