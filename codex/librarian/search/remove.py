"""Search Index cleanup."""

from time import time

from humanize import naturaldelta

from codex.librarian.search.status import SearchIndexStatusTypes
from codex.models import Comic
from codex.models.comic import ComicFTS
from codex.status import Status
from codex.threads import QueuedThread


class RemoveMixin(QueuedThread):
    """Search Index cleanup methods."""

    def __init__(self, abort_event, *args, **kwargs):
        """Initialize search engine."""
        self.abort_event = abort_event
        super().__init__(*args, **kwargs)

    def clear_search_index(self):
        """Clear the search index."""
        clear_status = Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)
        self.status_controller.start(clear_status)
        ComicFTS.objects.all().delete()
        self.status_controller.finish(clear_status)
        self.log.info("Old search index cleared.")

    def _remove_stale_records(self, status):  # type: ignore
        """Remove records not in the database from the index."""
        start_time = time()
        delete_comicfts = ComicFTS.objects.exclude(comic__in=Comic.objects.all())
        self.status_controller.update(status, notify=False)
        status.total = len(delete_comicfts)
        count, _ = delete_comicfts.delete()

        # Finish
        if count:
            elapsed_time = time() - start_time
            elapsed = naturaldelta(elapsed_time)
            cps = int(count / elapsed_time)
            self.log.info(
                f"Removed {count} stale records from the search index"
                f" in {elapsed} at {cps} per second."
            )
        else:
            self.log.debug("No stale records to remove from the search index.")

    def remove_stale_records(self):
        """Remove records not in the database from the index, trapping exceptions."""
        self.abort_event.clear()
        status = Status(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE)
        try:
            self._remove_stale_records(status)
        except Exception:
            self.log.exception("Removing stale records:")
        finally:
            self.status_controller.finish(status)
