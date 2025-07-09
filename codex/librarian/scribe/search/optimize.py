"""Search Index cleanup."""

from django.db import connection

from codex.librarian.scribe.search.status import SearchIndexOptimizeStatus
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
        status = SearchIndexOptimizeStatus()
        try:
            self.status_controller.update(status)
            self.log.info("Optimizing search index...")
            with connection.cursor() as cursor:
                cursor.execute(_OPTIMIZE_SQL)
        except Exception:
            self.log.exception("Removing stale records:")
        finally:
            self.status_controller.finish(status)
