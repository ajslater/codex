"""Sends notifications to connections, reading from a queue."""

from codex.librarian.bookmark.tasks import BookmarkUpdateTask
from codex.librarian.bookmark.update import BookmarkUpdate
from codex.threads import AggregateMessageQueuedThread


class BookmarkThread(AggregateMessageQueuedThread, BookmarkUpdate):
    """Aggregates Bookmark updates preventing floods updates db in batches.."""

    FLOOD_DELAY = 3.0
    MAX_DELAY = 5.0

    def aggregate_items(self, item):
        """Aggregate bookmark updates."""
        if isinstance(item, BookmarkUpdateTask):
            key = (tuple(item.auth_filter.items()), tuple(item.comic_filter.items()))
            if key not in self.cache:
                self.cache[key] = {}
            self.cache[key].update(item.updates)
        else:
            self.log.warning(f"Unknown Bookmark task {item}")

    def send_all_items(self):
        """Run the task method."""
        cleanup = set()
        for filters, updates in self.cache.items():
            try:
                auth_filter, comic_filter = filters
                auth_filter = dict(auth_filter)
                comic_filter = dict(comic_filter)
                self.update_bookmarks(auth_filter, comic_filter, updates)
                self.log.debug(f"updated {auth_filter | comic_filter}")
                cleanup.add(filters)
            except Exception:
                self.log.exception("Updating bookmarks")

        self.cleanup_cache(cleanup)
