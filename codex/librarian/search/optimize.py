"""Search Index cleanup."""

from time import time

from django.db import connection
from humanize import naturaldelta

from codex.librarian.janitor.tasks import JanitorSearchOptimizeFinishedTask
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.status import Status
from codex.threads import QueuedThread

_TABLE = "codex_comicfts"
_OPTIMIZE_SQL = f"INSERT INTO {_TABLE}({_TABLE}) VALUES('optimize')"


class OptimizeMixin(QueuedThread):
    """Search Index optimize methods."""

    def __init__(self, abort_event, *args, **kwargs):
        """Initialize search engine."""
        self.abort_event = abort_event
        super().__init__(*args, **kwargs)

    def optimize(self, janitor=False):
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
            self.log.info(f"Optimized search index in {elapsed}.")
        except Exception:
            self.log.exception("Removing stale records:")
        finally:
            self.status_controller.finish(status)
            if janitor:
                task = JanitorSearchOptimizeFinishedTask()
                self.librarian_queue.put(task)
