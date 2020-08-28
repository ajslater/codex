"""Library process worker for background tasks."""
import logging
import platform
import time

from multiprocessing import Pool
from multiprocessing import Process
from multiprocessing import set_start_method
from time import sleep

import simplejson as json

from django.apps import apps
from websocket import create_connection


if not apps.ready:
    import django

    django.setup()

from multiprocessing import Value

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
from codex.librarian.queue import ScannerCronTask
from codex.librarian.queue import ScanRootTask
from codex.librarian.queue import WatcherCronTask
from codex.librarian.scanner import scan_cron
from codex.librarian.scanner import scan_root
from codex.librarian.watcherd import Uatu
from codex.models import Comic
from codex.models import Folder
from codex.websocket_server import BROADCAST_MSG
from codex.websocket_server import BROADCAST_SECRET
from codex.websocket_server import LIBRARY_CHANGED_MSG
from codex.websocket_server import SCAN_ROOT_MSG
from codex.websocket_server import UNSUBSCRIBE_MSG
from codex.websocket_server import WS_API_PATH


# from django.utils.autoreload import file_changed


LOG = logging.getLogger(__name__)
PORT = Value("i", 9810)  # Shared memory overwritten in run.py
BROADCAST_URL_TMPL = "ws://localhost:{port}/" + WS_API_PATH
SHUTDOWN_MSG = "shutdown"
MAX_WS_ATTEMPTS = 4
librarian_proc = None
if platform.system() == "Darwin":
    # XXX Fixes QUEUE sharing with default spawn start method. The spawn
    # method is also very very slow. Use fork and the
    # OBJC_DISABLE_INITIALIZE_FORK_SAFETY environment variable for macOS.
    # https://bugs.python.org/issue40106
    set_start_method("fork", force=True)


def get_websocket():
    """Connect to the websocket broadcast url."""
    # XXX Its just easy to do this with the same ws server event loop
    #     instead of shared memory.
    ws = None
    attempts = 0
    while ws is None or not ws.connected and attempts <= MAX_WS_ATTEMPTS:
        time.sleep(0.5)
        try:
            broadcast_url = BROADCAST_URL_TMPL.format(port=PORT.value)
            ws = create_connection(broadcast_url)
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
    pool = Pool()

    while run:
        task = QUEUE.get()
        try:
            if isinstance(task, ScanRootTask):
                ws = send_json(ws, BROADCAST_MSG, SCAN_ROOT_MSG)
                scan_root(task.library_id, task.force)
            elif isinstance(task, ComicModifiedTask):
                import_comic(task.library_id, task.src_path)
            elif isinstance(task, ComicCoverCreateTask):
                # Cover creation is cpu bound, farm it out.
                pool.apply_async(
                    create_comic_cover,
                    args=(task.src_path, task.db_cover_path),
                )
            elif isinstance(task, FolderMovedTask):
                obj_moved(task.src_path, task.dest_path, Folder)
            elif isinstance(task, ComicMovedTask):
                obj_moved(task.src_path, task.dest_path, Comic)
            elif isinstance(task, ComicDeletedTask):
                obj_deleted(task.src_path, Comic)
            elif isinstance(task, FolderDeletedTask):
                obj_deleted(task.src_path, Folder)
            elif isinstance(task, LibraryChangedTask):
                ws = send_json(ws, BROADCAST_MSG, LIBRARY_CHANGED_MSG)
            elif isinstance(task, WatcherCronTask):
                sleep(task.sleep)
                watcher.set_all_library_watches()
            elif isinstance(task, ScannerCronTask):
                sleep(task.sleep)
                scan_cron()
            elif task == SHUTDOWN_MSG:
                run = False
            else:
                LOG.warning(f"Unhandled task popped: {task}")
        except (Comic.DoesNotExist, Folder.DoesNotExist) as exc:
            LOG.warning(exc)
        except Exception as exc:
            LOG.exception(exc)
    pool.close()
    crond.stop()
    watcher.stop()
    crond.join()
    watcher.join()
    pool.join()
    LOG.info("Stopped Librarian.")


def start_librarian():
    """Start the worker process."""
    global librarian_proc
    librarian_proc = Process(target=librarian, name="codex-librarian", daemon=False)
    librarian_proc.start()
    # this signal is thrown by runserver which i don't use anymore
    # file_changed.connect(stop_librarian)


def stop_librarian(*args, **kwargs):
    """Stop the librarian process."""
    global librarian_proc
    QUEUE.put(SHUTDOWN_MSG)
    if librarian_proc:
        librarian_proc.join()
