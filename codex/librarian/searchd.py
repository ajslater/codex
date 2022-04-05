"""Haystack Search index updater."""
import os

from datetime import datetime

from django.core.management import call_command
from django.utils import timezone

from codex.darwin_mp import force_darwin_multiprocessing_fork
from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    SearchIndexRebuildIfDBChangedTask,
    SearchIndexUpdateTask,
)
from codex.models import LatestVersion, Library, SearchResult
from codex.settings.logging import get_logger
from codex.settings.settings import CACHE_PATH, XAPIAN_INDEX_PATH
from codex.threads import QueuedThread


SEARCH_INDEX_TIMESTAMP_PATH = CACHE_PATH / "search_index_timestamp"
UPDATE_INDEX_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%Z"
LOG = get_logger(__name__)
WORKERS = os.cpu_count()
VERBOSITY = 1


def update_search_index(rebuild=False):
    """Update the search index."""
    try:
        any_update_in_progress = Library.objects.filter(
            update_in_progress=True
        ).exists()
        if any_update_in_progress:
            LOG.verbose("Database update in progress, not updating search index yet.")
            return

        XAPIAN_INDEX_PATH.mkdir(parents=True, exist_ok=True)

        if rebuild:
            LOG.verbose("Rebuilding search index...")
            call_command(
                "rebuild_index",
                interactive=False,
                workers=WORKERS,
                verbosity=VERBOSITY,
            )
            LatestVersion.set_xapian_index_version()
        else:
            try:
                timestamp = SEARCH_INDEX_TIMESTAMP_PATH.stat().st_mtime
            except FileNotFoundError:
                timestamp = 0
            start = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
                UPDATE_INDEX_DATETIME_FORMAT
            )

            LOG.verbose(f"Updating search index since {start}...")
            # Workers are only possible with fork()
            # django-haystack has a bug
            # https://github.com/django-haystack/django-haystack/issues/1650
            call_command(
                "update_index",
                "codex",
                remove=True,
                start=start,
                workers=WORKERS,
                verbosity=VERBOSITY,
            )
        SEARCH_INDEX_TIMESTAMP_PATH.touch()

        # Nuke the Search Result table as it's now out of date.
        SearchResult.truncate_and_reset()
        LOG.verbose("Finished updating search index.")
    except Exception as exc:
        LOG.error(f"Update search index: {exc}")


def rebuild_search_index_if_db_changed():
    """Rebuild the search index if the db changed."""
    if not LatestVersion.is_xapian_uuid_match():
        LOG.warning("Database does not match search index.")
        task = SearchIndexUpdateTask(True)
        LIBRARIAN_QUEUE.put(task)
    else:
        LOG.verbose("Database matches search index.")


class SearchIndexer(QueuedThread):
    """A worker to handle search index update tasks."""

    NAME = "SearchIndexer"

    def process_item(self, task):
        """Run the updater."""
        if isinstance(task, SearchIndexRebuildIfDBChangedTask):
            rebuild_search_index_if_db_changed()
        elif isinstance(task, SearchIndexUpdateTask):
            update_search_index(rebuild=task.rebuild)
        else:
            LOG.warning(f"Bad task sent to search index thread: {task}")

    def run(self):  # TODO maybe redundant now
        """Run the multiprocessing start method change for haystack update_index."""
        force_darwin_multiprocessing_fork()
        super().run()
