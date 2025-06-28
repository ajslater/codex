"""Search Index cleanup."""

from codex.librarian.scribe.search.optimize import SearchIndexerOptimize
from codex.librarian.scribe.search.status import SearchIndexStatusTypes
from codex.librarian.status import Status
from codex.models.comic import ComicFTS


class SearchIndexerRemove(SearchIndexerOptimize):
    """Search Index cleanup methods."""

    def clear_search_index(self):
        """Clear the search index."""
        clear_status = Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)
        self.status_controller.start(clear_status)
        ComicFTS.objects.all().delete()
        self.status_controller.finish(clear_status)
        self.log.success("Old search index cleared.")

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

        # Finish
        if count:
            reason = (
                f"Removed {count} stale records from the search index"
                f" in {status.elapsed()} at {status.per_second('records')}."
            )
            self.log.info(reason)
        else:
            self.log.debug("Removed no stale records from the search index.")

    def remove_stale_records(self):
        """Remove records not in the database from the index, trapping exceptions."""
        status = Status(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE)
        try:
            self._remove_stale_records(status)
        except Exception:
            self.log.exception("Removing stale records:")
        finally:
            self.status_controller.finish(status)
