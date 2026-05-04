"""Sends notifications to connections, reading from a queue."""

from collections.abc import Collection, Iterable
from datetime import datetime

from django.db.models.expressions import F
from django.db.models.query import Q
from django.utils import timezone as django_timezone

from codex.choices.notifications import Notifications
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import NotifierTask
from codex.models import Bookmark, Comic
from codex.views.auth import GroupACLMixin

_BOOKMARK_UPDATE_FIELDS = frozenset(
    {
        "page",
        "finished",
    }
)


class BookmarkUpdateMixin(GroupACLMixin):
    """Update Bookmarks."""

    # Used by Bookmarkd and view.bookmark.

    @staticmethod
    def _normalize_comic_pks(comic_pks) -> tuple[int, ...]:
        """
        Coerce QuerySet / Iterable inputs to a tuple of pks.

        Browser callers (``codex/views/browser/bookmark.py``) pass a
        ``Comic`` ``QuerySet``; the bookmark thread passes a tuple
        already. Forcing the QuerySet here costs one ``SELECT pk``
        but lets the rest of the flow do set arithmetic without
        re-evaluating Django expressions.
        """
        if isinstance(comic_pks, tuple):
            return comic_pks
        if hasattr(comic_pks, "values_list"):
            return tuple(comic_pks.values_list("pk", flat=True))
        return tuple(comic_pks)

    @classmethod
    def _get_existing_bookmarks_for_update(
        cls, auth_filter, comic_pks: Collection[int], updates
    ) -> tuple:
        # Get existing bookmarks
        query_filter = Q(**auth_filter) & Q(comic__in=comic_pks)
        existing_bookmarks = Bookmark.objects.filter(query_filter)
        if updates.get("page") is not None:
            existing_bookmarks = existing_bookmarks.annotate(
                page_count=F("comic__page_count")
            )

        update_fields = (set(updates.keys()) & _BOOKMARK_UPDATE_FIELDS) | {"updated_at"}
        # ``comic_id`` is loaded so the caller can build the
        # covered-pk set without a second SELECT.
        only_fields = (*update_fields, "pk", "comic_id")

        existing_bookmarks = existing_bookmarks.only(*only_fields)
        return existing_bookmarks, update_fields

    @classmethod
    def _prepare_bookmark_updates(
        cls, existing_bookmarks: Iterable, updates, now: datetime
    ) -> tuple[list, set[int]]:
        """
        Build the bulk_update objects and track covered comic ids.

        Returning the comic-id set lets the caller compute "missing"
        without a second SELECT — the create-path query only fires when
        phase 1 didn't already cover every input pk.
        """
        update_bookmarks = []
        covered_comic_ids: set[int] = set()
        for bm in existing_bookmarks:
            cls._update_bookmarks_validate_page(bm, updates)
            for key, value in updates.items():
                setattr(bm, key, value)
            # Single Python timestamp for the whole batch — bulk_update
            # otherwise emits ``NOW()`` per row in the generated CASE
            # WHEN, which is correct but redundant. A constant is also
            # easier to reason about for tests / mocks.
            bm.updated_at = now
            update_bookmarks.append(bm)
            covered_comic_ids.add(bm.comic_id)
        return update_bookmarks, covered_comic_ids

    @staticmethod
    def _update_bookmarks_validate_page(bm, updates) -> None:
        """Force bookmark page into valid range."""
        page = updates.get("page")
        if page is None:
            return
        max_page = bm.page_count + 1
        page = max(min(page, max_page), 0)
        if page == max_page:
            # Auto finish on bookmark last page
            bm.finished = True
        updates["page"] = page

    @staticmethod
    def _notify_library_changed(uid) -> None:
        """Notify one user that their library changed."""
        group = f"user_{uid}"
        task = NotifierTask(Notifications.BOOKMARK.value, group)
        LIBRARIAN_QUEUE.put(task)

    @classmethod
    def _update_bookmarks(
        cls, auth_filter, comic_pks: Collection[int], updates, now: datetime
    ) -> tuple[int, set[int]]:
        """Update existing bookmarks; return (count, covered_comic_ids)."""
        if not updates:
            return 0, set()

        existing_bookmarks, update_fields = cls._get_existing_bookmarks_for_update(
            auth_filter, comic_pks, updates
        )
        update_bookmarks, covered = cls._prepare_bookmark_updates(
            existing_bookmarks, updates, now
        )
        count = len(update_bookmarks)
        if count:
            Bookmark.objects.bulk_update(update_bookmarks, tuple(update_fields))
        return count, covered

    @classmethod
    def _get_comics_without_bookmarks(cls, missing_comic_pks: Collection[int]):
        """Pk-only Comic queryset for the create path."""
        # Phase 1 already proved these pks have no matching bookmark
        # for the auth_filter, so the previous ``~Q(bookmark__user_id=...)``
        # subquery is redundant — one straight pk lookup suffices.
        return Comic.objects.filter(pk__in=missing_comic_pks).only("pk")

    @classmethod
    def _prepare_bookmark_creates(
        cls, create_bookmark_comics, auth_filter, updates
    ) -> list:
        # Prepare creates
        create_bookmarks = []
        for comic in create_bookmark_comics:
            bm = Bookmark(comic=comic, **auth_filter, **updates)
            create_bookmarks.append(bm)
        return create_bookmarks

    @classmethod
    def _create_bookmarks(
        cls, auth_filter, missing_comic_pks: Collection[int], updates
    ) -> int:
        """Create new bookmarks for comics that don't have one yet."""
        if not updates or not missing_comic_pks:
            return 0

        create_bookmark_comics = cls._get_comics_without_bookmarks(missing_comic_pks)
        create_bookmarks = cls._prepare_bookmark_creates(
            create_bookmark_comics, auth_filter, updates
        )
        count = len(create_bookmarks)
        if count:
            # ``bulk_create`` here is a plain INSERT path; no UPSERT.
            # Schema-side, ``Bookmark.unique_together = (user, session,
            # comic)`` has nullable user/session, and SQLite (like ANSI
            # SQL) treats NULLs in unique indexes as distinct — so an
            # ``ON CONFLICT DO UPDATE`` target wouldn't fire for a row
            # whose ``session_id`` is NULL on both sides. The two-pass
            # design (filter existing first, only insert truly missing
            # rows) sidesteps that gotcha.
            Bookmark.objects.bulk_create(create_bookmarks)
        return count

    @classmethod
    def update_bookmarks(cls, auth_filter, comic_pks, updates) -> int:
        """Update a user bookmark."""
        if not updates:
            return 0
        comic_pks = cls._normalize_comic_pks(comic_pks)
        if not comic_pks:
            return 0

        # Single Python timestamp for the whole batch — both phases
        # share it so ``updated_at`` stays consistent across the
        # update + create halves of the operation.
        now = django_timezone.now()

        update_count, covered = cls._update_bookmarks(
            auth_filter, comic_pks, updates, now
        )
        # Skip the create-path SELECT entirely when phase 1 already
        # covered every input pk — the hot path on a sequential read
        # (page 2..N of one comic) hits this branch every time after
        # the first bookmark is created.
        missing_pks = set(comic_pks) - covered
        create_count = cls._create_bookmarks(auth_filter, missing_pks, updates)

        count = update_count + create_count
        if count:
            uid = next(iter(auth_filter.values()))
            cls._notify_library_changed(uid)
        return count
