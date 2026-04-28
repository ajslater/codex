"""Sends notifications to connections, reading from a queue."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import override

from loguru import logger

from codex.librarian.bookmark.latest_version import CodexLatestVersionUpdater
from codex.librarian.bookmark.tasks import (
    BookmarkUpdateTask,
    ClearLibrarianStatusTask,
    CodexLatestVersionTask,
    UserActiveTask,
)
from codex.librarian.bookmark.update import BookmarkUpdateMixin
from codex.librarian.bookmark.user_active import UserActiveMixin
from codex.librarian.telemeter.tasks import TelemeterTask
from codex.librarian.telemeter.telemeter import send_telemetry
from codex.librarian.threads import AggregateMessageQueuedThread


@dataclass
class BookmarkKey:
    """
    Bookmark queue item key.

    Identity is field-equality on ``(auth_filter, comic_pks, user_pk)``.
    The hash is computed once at construction and cached: ``__hash__``
    is called per cache-key lookup, and rebuilding
    ``tuple(auth_filter.items())`` per call wastes work on a hot path.
    """

    auth_filter: Mapping[str, int | str | None] | None = None
    comic_pks: tuple = ()
    user_pk: int = 0
    # Excluded from compare/init/repr — pure derived data populated in
    # ``__post_init__``. Keeping it on the dataclass means the cache
    # lives for the instance's lifetime without an extra dict.
    _hash: int = field(default=0, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Cache a stable hash of the identity tuple."""
        # ``sorted()`` makes the hash stable regardless of dict insertion
        # order — defensive against ``{"user_id": 1}`` / ``{"session_id":
        # ...}`` shape drift.
        auth_filter_key = (
            None
            if self.auth_filter is None
            else tuple(sorted(self.auth_filter.items()))
        )
        object.__setattr__(
            self,
            "_hash",
            hash((auth_filter_key, self.comic_pks, self.user_pk)),
        )

    @override
    def __hash__(self) -> int:
        """Return the cached identity hash."""
        return self._hash

    @override
    def __eq__(self, other) -> bool:
        """
        Compare by identity fields, not by hash.

        The previous implementation returned
        ``self.__hash__() == other.__hash__()`` — collision-vulnerable.
        Two distinct keys that hash-collide would compare equal and the
        aggregator would merge one user's bookmark into another user's
        cache entry, then write to that other user's DB row.
        """
        if not isinstance(other, BookmarkKey):
            return NotImplemented
        return (
            self.auth_filter == other.auth_filter
            and self.comic_pks == other.comic_pks
            and self.user_pk == other.user_pk
        )


class BookmarkThread(
    AggregateMessageQueuedThread,
    BookmarkUpdateMixin,
    UserActiveMixin,
):
    """Aggregates Bookmark updates preventing floods updates db in batches.."""

    FLOOD_DELAY = 3.0
    MAX_DELAY = 5.0

    def __init__(self, *args, **kwargs) -> None:
        """Init mixins."""
        super().__init__(*args, **kwargs)
        self.init_group_acl()
        self.init_user_active()

    def _process_task_immediately(self, task) -> None:
        if self.db_write_lock.locked():
            self.log.warning(f"Database locked, not processing {task}")
        match task:
            case TelemeterTask():
                send_telemetry(self.log)
            case ClearLibrarianStatusTask():
                self.status_controller.finish_many([])
            case CodexLatestVersionTask():
                worker = CodexLatestVersionUpdater(
                    self.log, self.librarian_queue, self.db_write_lock
                )
                worker.update_latest_version(force=task.force)
            case _:
                self.log.warning(f"Unknown Bookmark task {task}")

    @override
    def aggregate_items(self, item) -> None:
        """Aggregate bookmark updates."""
        task = item
        match task:
            case UserActiveTask():
                # Wedge the user active recorer into the bookmark thread because it
                # it also wants to be done offline and low priority.
                key = BookmarkKey(user_pk=item.pk)
                self.cache[key] = None
            case BookmarkUpdateTask():
                key = BookmarkKey(item.auth_filter, item.comic_pks)
                if key not in self.cache:
                    self.cache[key] = {}
                self.cache[key].update(item.updates)
            case _:
                self._process_task_immediately(task)

    @override
    def send_all_items(self) -> None:
        """Run the task method."""
        if self.db_write_lock.locked():
            self.log.debug("Database locked, waiting to process bookmarks.")
            return
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
