"""Search Index cleanup."""

from django.db import connection

from codex.librarian.scribe.search.status import SearchIndexOptimizeStatus
from codex.librarian.worker import (
    WorkerStatusAbortableBase,
)

_TABLE = "codex_comicfts"
_OPTIMIZE_SQL = f"INSERT INTO {_TABLE}({_TABLE}) VALUES('optimize')"


class SearchIndexerOptimize(WorkerStatusAbortableBase):
    """Search Index optimize methods."""

    def optimize(self):
        """Remove records not in the database from the index, trapping exceptions."""
        status = SearchIndexOptimizeStatus()
        try:
            self.status_controller.start(status)
            with connection.cursor() as cursor:
                cursor.execute(_OPTIMIZE_SQL)
        except Exception:
            self.log.exception("Optimizing search index:")
        finally:
            self.status_controller.finish(status)
