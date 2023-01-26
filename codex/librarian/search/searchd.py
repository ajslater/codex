"""Haystack Search index updater."""
from datetime import datetime
from multiprocessing import Process
from uuid import uuid4

from django.core.management import call_command
from haystack import connections as haystack_connections
from humanize import naturaldelta

from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.tasks import (
    SearchIndexOptimizeTask,
    SearchIndexRebuildIfDBChangedTask,
    SearchIndexUpdateTask,
)
from codex.librarian.status_control import StatusControl
from codex.models import Library, Timestamp
from codex.search.backend import CodexSearchBackend
from codex.settings.logging import get_logger
from codex.settings.settings import SEARCH_INDEX_PATH, SEARCH_INDEX_UUID_PATH
from codex.threads import QueuedThread


UPDATE_INDEX_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%Z"
LOG = get_logger(__name__)
VERBOSITY = 1
REBUILD_ARGS = ("rebuild_index",)
REBUILD_KWARGS = {"interactive": False, "verbosity": VERBOSITY}
UPDATE_ARGS = ("update_index", "codex")
UPDATE_KWARGS = {
    "remove": True,
    "verbosity": VERBOSITY,
}
MIN_FINISHED_TIME = 1
OPTIMIZE_DOC_COUNT = 10000


def _set_search_index_version():
    """Set the codex db to search index matching id."""
    version = str(uuid4())
    try:
        lv = Timestamp.objects.get(name=Timestamp.SEARCH_INDEX_UUID)
        lv.version = version
        lv.save()
        SEARCH_INDEX_PATH.mkdir(parents=True, exist_ok=True)
        with SEARCH_INDEX_UUID_PATH.open("w") as uuid_file:
            uuid_file.write(version)
    except Exception as exc:
        LOG.error(f"Setting search index to db synchronization token: {exc}")


def _is_search_index_uuid_match():
    """Is this search index for this database."""
    result = False
    try:
        with SEARCH_INDEX_UUID_PATH.open("r") as uuid_file:
            version = uuid_file.read()
        result = Timestamp.objects.filter(
            name=Timestamp.SEARCH_INDEX_UUID, version=version
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


def _update_search_index(rebuild=False):
    """Update the search index."""
    try:
        any_update_in_progress = Library.objects.filter(
            update_in_progress=True
        ).exists()
        if any_update_in_progress:
            LOG.verbose("Database update in progress, not updating search index yet.")
            return

        if not rebuild and not _is_search_index_uuid_match():
            LOG.warning("Database does not match search index.")
            rebuild = True

        SEARCH_INDEX_PATH.mkdir(parents=True, exist_ok=True)

        if rebuild:
            LOG.verbose("Rebuilding search index...")
            _call_command(REBUILD_ARGS, REBUILD_KWARGS)
            _set_search_index_version()
        else:
            start = Timestamp.objects.get(
                name=Timestamp.SEARCH_INDEX
            ).updated_at.strftime(UPDATE_INDEX_DATETIME_FORMAT)
            LOG.verbose(f"Updating search index since {start}...")
            # Workers are only possible with fork()
            # django-haystack has a bug
            # https://github.com/django-haystack/django-haystack/issues/1650
            kwargs = {"start": start}
            kwargs.update(UPDATE_KWARGS)
            _call_command(UPDATE_ARGS, kwargs)
        Timestamp.touch(Timestamp.SEARCH_INDEX)

        LOG.verbose("Finished updating search index.")
    except Exception as exc:
        LOG.error(f"Update search index: {exc}")


def _rebuild_search_index_if_db_changed():
    """Rebuild the search index if the db changed."""
    if not _is_search_index_uuid_match():
        LOG.warning("Database does not match search index.")
        task = SearchIndexUpdateTask(True)
        LIBRARIAN_QUEUE.put(task)
    else:
        LOG.verbose("Database matches search index.")


def _optimize_search_index(force=False):
    """Optimize search index."""
    try:
        StatusControl.start(type=SearchIndexStatusTypes.SEARCH_INDEX_OPTIMIZE)
        LOG.verbose("Optimizing search index...")
        start = datetime.now()
        num_segments = len(tuple(SEARCH_INDEX_PATH.glob("*.seg")))
        if num_segments <= 1:
            LOG.verbose("Search index already optimized.")
            return
        backends = haystack_connections.connections_info.keys()
        for conn_key in backends:
            backend = haystack_connections[conn_key].get_backend()
            if not backend.setup_complete:
                backend.setup()
            backend.index = backend.index.refresh()
            num_docs = backend.index.doc_count()
            if num_docs > OPTIMIZE_DOC_COUNT and not force:
                LOG.verbose(
                    f"Search index > {OPTIMIZE_DOC_COUNT} comics. Not optimizing."
                )
                return
            LOG.verbose(f"Search index found in {num_segments} segments.")
            writerargs = CodexSearchBackend.get_writerargs(num_docs)
            backend.index.optimize(**writerargs)
            elapsed_delta = datetime.now() - start
            elapsed = naturaldelta(elapsed_delta)
            cps = int(num_docs / elapsed_delta.total_seconds())
            LOG.info(f"Optimized search index in {elapsed} at {cps} comics per second.")
    finally:
        StatusControl.finish(SearchIndexStatusTypes.SEARCH_INDEX_OPTIMIZE)


class SearchIndexer(QueuedThread):
    """A worker to handle search index update tasks."""

    NAME = "SearchIndexer"  # type: ignore

    def process_item(self, task):
        """Run the updater."""
        if isinstance(task, SearchIndexRebuildIfDBChangedTask):
            _rebuild_search_index_if_db_changed()
        elif isinstance(task, SearchIndexUpdateTask):
            _update_search_index(rebuild=task.rebuild)
        elif isinstance(task, SearchIndexOptimizeTask):
            _optimize_search_index(task.force)
        else:
            LOG.warning(f"Bad task sent to search index thread: {task}")
