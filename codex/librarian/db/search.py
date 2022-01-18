"""Haystack Search index updater."""
import os

from datetime import datetime
from logging import getLogger

from django.core.management import call_command
from django.utils import timezone

from codex.models import LatestVersion, SearchResult
from codex.settings.settings import CACHE_PATH, XAPIAN_INDEX_PATH


SEARCH_INDEX_TIMESTAMP_PATH = CACHE_PATH / "search_index_timestamp"
UPDATE_INDEX_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%Z"
LOG = getLogger(__name__)


def update_search_index(rebuild=False):
    """Update the search index."""
    XAPIAN_INDEX_PATH.mkdir(parents=True, exist_ok=True)

    if rebuild:
        LOG.verbose("Rebuilding search index...")  # type: ignore
        call_command(
            "rebuild_index",
            interactive=False,
            workers=os.cpu_count(),
            verbosity=1,
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

        LOG.verbose(f"Updating search index since {start}...")  # type: ignore
        # Workers are only possible with fork()
        # django-haystack has a bug
        # https://github.com/django-haystack/django-haystack/issues/1650
        call_command(
            "update_index",
            "codex",
            remove=True,
            start=start,
            workers=os.cpu_count(),
            verbosity=1,
        )
    SEARCH_INDEX_TIMESTAMP_PATH.touch()

    # Nuke the Search Result table as it's now out of date.
    SearchResult.truncate_and_reset()
    LOG.verbose("Updated search index.")  # type: ignore


def rebuild_search_index_if_db_changed():
    """Rebuild the search index if the db changed."""
    if LatestVersion.is_xapian_uuid_match():
        LOG.verbose("Database matches search index.")  # type: ignore
        return
    else:
        LOG.warning("Database does not match search index.")
    update_search_index(rebuild=True)
