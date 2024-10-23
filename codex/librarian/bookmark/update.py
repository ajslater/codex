"""Sends notifications to connections, reading from a queue."""

from django.contrib.auth.models import User
from django.db.models.expressions import F
from django.db.models.functions import Now
from django.db.models.query import Q

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import NotifierTask
from codex.models import Bookmark, Comic
from codex.models.admin import UserActive
from codex.views.auth import GroupACLMixin

_VERTICAL_READING_DIRECTIONS = frozenset({"ttb", "btt"})
_BOOKMARK_UPDATE_FIELDS = frozenset(
    {
        "page",
        "finished",
        "fit_to",
        "two_pages",
        "reading_direction",
    }
)


class BookmarkUpdate(GroupACLMixin):
    """Update Bookmarks."""

    # Used by Bookmarkd and view.bookmark.

    @staticmethod
    def _update_bookmarks_validate_page(bm, updates):
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
    def _update_bookmarks_validate_two_pages(bm, updates):
        """Force vertical view to not use two pages."""
        rd = updates.get("reading_direction")
        if bm.two_pages and bool(
            {rd, bm.reading_direction}.intersection(_VERTICAL_READING_DIRECTIONS)
        ):
            updates["two_pages"] = None

    @staticmethod
    def _notify_library_changed(uid):
        """Notify one user that their library changed."""
        group = f"user_{uid}"
        task = NotifierTask("LIBRARY_CHANGED", group)
        LIBRARIAN_QUEUE.put(task)

    @classmethod
    def _update_bookmarks(cls, auth_filter, comic_pks, updates, user) -> int:
        """Update existing bookmarks."""
        count = 0
        if not updates:
            return count
        group_acl_filter = cls.get_group_acl_filter(Bookmark, user)
        query_filter = group_acl_filter & Q(**auth_filter) & Q(comic__in=comic_pks)
        existing_bookmarks = Bookmark.objects.filter(query_filter)
        if updates.get("page") is not None:
            existing_bookmarks = existing_bookmarks.annotate(
                page_count=F("comic__page_count")
            )

        update_fields = set(updates.keys()) & _BOOKMARK_UPDATE_FIELDS
        update_fields.add("updated_at")
        only_fields = (*update_fields, "pk")

        existing_bookmarks = existing_bookmarks.only(*only_fields)
        update_bookmarks = []
        for bm in existing_bookmarks:
            cls._update_bookmarks_validate_page(bm, updates)
            cls._update_bookmarks_validate_two_pages(bm, updates)
            for key, value in updates.items():
                setattr(bm, key, value)
            bm.updated_at = Now()
            update_bookmarks.append(bm)
        count = len(update_bookmarks)
        if count:
            Bookmark.objects.bulk_update(update_bookmarks, tuple(update_fields))
        return count

    @staticmethod
    def _create_bookmarks_validate_two_pages(updates):
        """Force vertical view to not use two pages."""
        if (
            updates.get("two_pages")
            and updates.get("reading_direction") in _VERTICAL_READING_DIRECTIONS
        ):
            updates.pop("two_pages", None)

    @classmethod
    def _create_bookmarks(cls, auth_filter, comic_pks, updates, user) -> int:
        """Create new bookmarks for comics that don't exist yet."""
        count = 0
        cls._create_bookmarks_validate_two_pages(updates)
        if not updates:
            return count
        create_bookmarks = []
        group_acl_filter = cls.get_group_acl_filter(Comic, user)
        exclude = {}
        for key, value in auth_filter.items():
            exclude["bookmark__" + key] = value
        query_filter = group_acl_filter & Q(pk__in=comic_pks) & ~Q(**exclude)
        create_bookmark_comics = Comic.objects.filter(query_filter).only("pk")
        for comic in create_bookmark_comics:
            bm = Bookmark(comic=comic, **auth_filter, **updates)
            create_bookmarks.append(bm)
        count = len(create_bookmarks)
        if count:
            Bookmark.objects.bulk_create(
                create_bookmarks,
                update_fields=tuple(_BOOKMARK_UPDATE_FIELDS),
                unique_fields=Bookmark._meta.unique_together[0],
            )
        return count

    @classmethod
    def _update_user_active(cls, user, log):
        """Update user active."""
        # Offline because profile gets hit rapidly in succession.
        try:
            UserActive.objects.update_or_create(user=user)
        except Exception as exc:
            reason = f"Update user activity {exc}"
            log.warning(reason)

    @classmethod
    def update_bookmarks(cls, auth_filter, comic_pks, updates, log):
        """Update a user bookmark."""
        user = None
        for key, value in auth_filter.items():
            if key == "user":
                user = User.objects.get(pk=value)
            break

        count = cls._update_bookmarks(auth_filter, comic_pks, updates, user)
        count += cls._create_bookmarks(auth_filter, comic_pks, updates, user)
        if user:
            cls._update_user_active(user, log)
        if count:
            uid = next(iter(auth_filter.values()))
            cls._notify_library_changed(uid)
        return count
