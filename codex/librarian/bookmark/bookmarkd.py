"""Sends notifications to connections, reading from a queue."""

from collections.abc import Mapping
from dataclasses import dataclass

from loguru import logger
from typing_extensions import override

from codex.librarian.bookmark.tasks import (
    BookmarkUpdateTask,
    UserActiveTask,
)
from codex.librarian.bookmark.update import BookmarkUpdateMixin
from codex.librarian.bookmark.user_active import UserActiveMixin
from codex.threads import AggregateMessageQueuedThread


@dataclass
class BookmarkKey:
    """Bookmark queue item key."""

    auth_filter: Mapping[str, int | str | None] | None = None
    comic_pks: tuple = ()
    user_pk: int = 0

    @override
    def __hash__(self):
        """Hash the dict as a tuple."""
        auth_filters = (
            None if self.auth_filter is None else tuple(self.auth_filter.items())
        )
        return hash((auth_filters, self.comic_pks, self.user_pk))

    @override
    def __eq__(self, other):
        """Equal uses hashes."""
        return self.__hash__() == other.__hash__()


class BookmarkThread(
    AggregateMessageQueuedThread,
    BookmarkUpdateMixin,
    UserActiveMixin,
):
    """Aggregates Bookmark updates preventing floods updates db in batches.."""

    FLOOD_DELAY = 3.0
    MAX_DELAY = 5.0

    def __init__(self, *args, **kwargs):
        """Init mixins."""
        super().__init__(*args, **kwargs)
        self.init_group_acl()
        self.init_user_active()

    @override
    def aggregate_items(self, item):
        """Aggregate bookmark updates."""
        if isinstance(item, UserActiveTask):
            # Wedge the user active recorer into the bookmark thread because it
            # it also wants to be done offline and low priority.
            key = BookmarkKey(user_pk=item.pk)
            self.cache[key] = None
        elif isinstance(item, BookmarkUpdateTask):
            key = BookmarkKey(item.auth_filter, item.comic_pks)
            if key not in self.cache:
                self.cache[key] = {}
            self.cache[key].update(item.updates)
        else:
            self.log.warning(f"Unknown Bookmark task {item}")

    @override
    def send_all_items(self):
        """Run the task method."""
        cleanup = set()
        for key, value in self.cache.items():
            try:
                if key.user_pk:
                    self.update_user_active(key.user_pk, logger)
                elif key.comic_pks:
                    self.update_bookmarks(key.auth_filter, key.comic_pks, value)
                cleanup.add(key)
            except Exception:
                self.log.exception("Updating bookmarks")

        self.cleanup_cache(cleanup)
