"""Library worker for for processing filesystem tasks from the queue."""
import logging

# from multiprocessing import Pool
from multiprocessing import Process

from django.utils.autoreload import file_changed

from codex.library.importer import import_comic
from codex.library.importer import obj_deleted
from codex.library.importer import obj_moved
from codex.library.queue import QUEUE
from codex.library.queue import ComicDeletedTask
from codex.library.queue import ComicModifiedTask
from codex.library.queue import ComicMovedTask
from codex.library.queue import FolderDeletedTask
from codex.library.queue import FolderMovedTask
from codex.library.queue import ScanRootTask
from codex.library.scanner import scan_root
from codex.models import Comic
from codex.models import Folder


LOG = logging.getLogger(__name__)
proc = None


def librarian():
    """Triage and process tasks from the queue."""
    # pool = Pool()
    while True:
        task = QUEUE.get()
        try:
            if isinstance(task, ScanRootTask):
                scan_root(task.root_path_id, task.force)
            elif isinstance(task, ComicModifiedTask):
                import_comic(task.root_path_id, task.src_path)
                # TODO use a higher performance db?
                # import is cpu bound, so farm it out.
                # pool.apply_async(import_comic,args=(task.root_path_id, task.src_path))
            elif isinstance(task, FolderMovedTask):
                obj_moved(task.src_path, task.dest_path, Folder)
            elif isinstance(task, ComicMovedTask):
                obj_moved(task.src_path, task.dest_path, Comic)
            elif isinstance(task, ComicDeletedTask):
                obj_deleted(task.src_path, Comic)
            elif isinstance(task, FolderDeletedTask):
                obj_deleted(task.src_path, Folder)
            else:
                LOG.warning(f"Unhandled task popped: {task}")
        except (Comic.DoesNotExist, Folder.DoesNotExist) as exc:
            LOG.warning(exc)
        except Exception as exc:
            LOG.exception(exc)


def stop_librarian(*args, **kwargs):
    """
    Stop the librarian process.

    Neccessary because it is a non-daemon thread.
    """
    proc.terminate()


def start_librarian():
    """Start the queue process."""
    global proc
    proc = Process(target=librarian, name="library-queue", daemon=True)
    proc.start()

    # django reload signal
    # TODO add another signal asgi stopping or keyboard interrupt
    #   if daphne has trouble stopping cleanly
    file_changed.connect(stop_librarian)

    LOG.info("Started Library Queue.")
