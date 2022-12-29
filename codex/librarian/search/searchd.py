"""Haystack Search index updater."""
import os

from datetime import datetime, timezone
from multiprocessing import Process
from uuid import uuid4

from django.core.management import call_command

from codex.librarian.queue_mp import LIBRARIAN_QUEUE, DelayedTasks
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.tasks import (
    SearchIndexJanitorUpdateTask,
    SearchIndexRebuildIfDBChangedTask,
)
from codex.librarian.status_control import StatusControl, StatusControlFinishTask
from codex.models import Library, SearchResult, Timestamp
from codex.settings.logging import get_logger
from codex.settings.settings import XAPIAN_INDEX_PATH, XAPIAN_INDEX_UUID_PATH
from codex.threads import QueuedThread


UPDATE_INDEX_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%Z"
LOG = get_logger(__name__)
WORKERS = os.cpu_count()
VERBOSITY = 1
REBUILD_ARGS = ("rebuild_index",)
REBUILD_KWARGS = {"interactive": False, "workers": WORKERS, "verbosity": VERBOSITY}
UPDATE_ARGS = ("update_index", "codex")
UPDATE_KWARGS = {
    "remove": True,
    "workers": WORKERS,
    "verbosity": VERBOSITY,
}
MIN_FINISHED_TIME = 1


def set_xapian_index_version():
    """Set the codex db to xapian matching id."""
    version = str(uuid4())
    try:
        lv = Timestamp.objects.get(name=Timestamp.XAPIAN_INDEX_UUID)
        lv.version = version
        lv.save()
        XAPIAN_INDEX_PATH.mkdir(parents=True, exist_ok=True)
        with XAPIAN_INDEX_UUID_PATH.open("w") as uuid_file:
            uuid_file.write(version)
    except Exception as exc:
        LOG.error(f"Setting search index to db synchronization token: {exc}")


def is_xapian_uuid_match():
    """Is this xapian index for this database."""
    result = False
    try:
        with XAPIAN_INDEX_UUID_PATH.open("r") as uuid_file:
            version = uuid_file.read()
        result = Timestamp.objects.filter(
            name=Timestamp.XAPIAN_INDEX_UUID, version=version
        ).exists()
    except (FileNotFoundError, Timestamp.DoesNotExist):
        pass
    except Exception as exc:
        LOG.exception(exc)
    return result


def _call_command(args, kwargs):
    """Call a command in a process to trap its zombies and errors."""
    proc = Process(target=call_command, args=args, kwargs=kwargs)
    proc.start()
    proc.join()
    proc.close()


def _get_latest_index_mtime():
    """Get the latest mtime for all files in the index dir."""
    latest_mtime = datetime.min
    for entry in os.scandir(XAPIAN_INDEX_PATH):
        if not entry.is_file():
            continue
        mtime = datetime.fromtimestamp(entry.stat().st_mtime)
        if mtime > latest_mtime:
            latest_mtime = mtime
    return latest_mtime


def update_search_index(rebuild=False):
    """Update the search index."""
    start_time = datetime.now()
    try:
        any_update_in_progress = Library.objects.filter(
            update_in_progress=True
        ).exists()
        if any_update_in_progress:
            LOG.verbose("Database update in progress, not updating search index yet.")
            return

        if not rebuild and not is_xapian_uuid_match():
            LOG.warning("Database does not match search index.")
            rebuild = True
        status_keys = {"type": SearchIndexStatusTypes.SEARCH_INDEX}
        if rebuild:
            status_keys["name"] = "rebuild"
        else:
            status_keys["name"] = "update"
        StatusControl.start(**status_keys)
        start_time = datetime.now()

        XAPIAN_INDEX_PATH.mkdir(parents=True, exist_ok=True)
        start_index_mtime = _get_latest_index_mtime()

        if rebuild:
            LOG.verbose("Rebuilding search index...")
            _call_command(REBUILD_ARGS, REBUILD_KWARGS)
            set_xapian_index_version()
        else:
            try:
                timestamp = Timestamp.get(Timestamp.SEARCH_INDEX)
            except FileNotFoundError:
                timestamp = 0
            start = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
                UPDATE_INDEX_DATETIME_FORMAT
            )

            LOG.verbose(f"Updating search index since {start}...")
            # Workers are only possible with fork()
            # django-haystack has a bug
            # https://github.com/django-haystack/django-haystack/issues/1650
            kwargs = {"start": start}
            kwargs.update(UPDATE_KWARGS)
            _call_command(UPDATE_ARGS, kwargs)
        Timestamp.touch(Timestamp.SEARCH_INDEX)

        end_index_mtime = _get_latest_index_mtime()
        if end_index_mtime > start_index_mtime:
            # Nuke the Search Result table if it's out of date.
            SearchResult.truncate_and_reset()
        LOG.verbose("Finished updating search index.")
    except Exception as exc:
        LOG.error(f"Update search index: {exc}")
    finally:
        # XXX this may solve a timing bug that left update index status unfinished
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed > MIN_FINISHED_TIME:
            delay = 0
        else:
            delay = MIN_FINISHED_TIME
        task = DelayedTasks(
            delay, (StatusControlFinishTask(SearchIndexStatusTypes.SEARCH_INDEX),)
        )
        LIBRARIAN_QUEUE.put(task)


def rebuild_search_index_if_db_changed():
    """Rebuild the search index if the db changed."""
    if not is_xapian_uuid_match():
        LOG.warning("Database does not match search index.")
        task = SearchIndexJanitorUpdateTask(True)
        LIBRARIAN_QUEUE.put(task)
    else:
        LOG.verbose("Database matches search index.")


class SearchIndexer(QueuedThread):
    """A worker to handle search index update tasks."""

    NAME = "SearchIndexer"  # type: ignore

    def process_item(self, task):
        """Run the updater."""
        if isinstance(task, SearchIndexRebuildIfDBChangedTask):
            rebuild_search_index_if_db_changed()
        elif isinstance(task, SearchIndexJanitorUpdateTask):
            update_search_index(rebuild=task.rebuild)
        else:
            LOG.warning(f"Bad task sent to search index thread: {task}")
