"""Search Index cleanup."""

from time import time

from django.db import connection
from humanize import naturaldelta

from codex.librarian.scribe.search.status import SearchIndexStatusTypes
from codex.librarian.status import Status
from codex.librarian.worker import WorkerStatusMixin

_TABLE = "codex_comicfts"
_OPTIMIZE_SQL = f"INSERT INTO {_TABLE}({_TABLE}) VALUES('optimize')"


class SearchIndexerOptimize(WorkerStatusMixin):
    """Search Index optimize methods."""

    def __init__(self, *args, event, **kwargs):
        """Initialize search engine."""
        self.abort_event = event
        self.init_worker(*args, **kwargs)

    def optimize(self):
        """Remove records not in the database from the index, trapping exceptions."""
        start_time = time()
        status = Status(SearchIndexStatusTypes.SEARCH_INDEX_OPTIMIZE)
        try:
            self.status_controller.update(status)
            self.log.info("Optimizing search index...")
            with connection.cursor() as cursor:
                cursor.execute(_OPTIMIZE_SQL)
            elapsed_time = time() - start_time
            elapsed = naturaldelta(elapsed_time)
            self.log.success(f"Optimized search index in {elapsed}.")
        except Exception:
            self.log.exception("Removing stale records:")
        finally:
            self.status_controller.finish(status)
