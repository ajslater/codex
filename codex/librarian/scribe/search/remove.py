"""Search Index cleanup."""

from codex.librarian.scribe.search.optimize import SearchIndexerOptimize
from codex.librarian.scribe.search.status import (
    SearchIndexCleanStatus,
    SearchIndexClearStatus,
)
from codex.models.comic import ComicFTS


class SearchIndexerRemove(SearchIndexerOptimize):
    """Search Index cleanup methods."""

    def clear_search_index(self):
        """Clear the search index."""
        clear_status = SearchIndexClearStatus()
        self.status_controller.start(clear_status)
        ComicFTS.objects.all().delete()
        self.status_controller.finish(clear_status)

    def _remove_stale_records(self, status):
        """Remove records not in the database from the index."""
        self.status_controller.start(status)
        self.log.debug("Finding stale records to remove...")
        delete_comicfts = ComicFTS.objects.filter(comic__isnull=True)
        status.total = delete_comicfts.count()
        self.status_controller.update(status)
        if status.total:
            self.log.debug(f"Removing {status.total} stale records...")
        count, _ = delete_comicfts.delete()
        status.complete = count
        return count

    def remove_stale_records(self) -> int:
        """Remove records not in the database from the index, trapping exceptions."""
        count = 0
        status = SearchIndexCleanStatus()
        try:
            count = self._remove_stale_records(status)
        except Exception:
            self.log.exception("Removing stale records:")
        finally:
            self.status_controller.finish(status)
        return count
