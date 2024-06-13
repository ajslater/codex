"""Bookmark views."""

from django.db.models.expressions import F
from django.db.models.functions import Now
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import NotifierTask
from codex.logger.logging import get_logger
from codex.models import Bookmark, Comic
from codex.serializers.models.bookmark import (
    BookmarkFinishedSerializer,
    BookmarkSerializer,
)
from codex.views.auth import (
    AuthFilterGenericAPIView,
)
from codex.views.const import FOLDER_GROUP, GROUP_RELATION

LOG = get_logger(__name__)
VERTICAL_READING_DIRECTIONS = frozenset({"ttb", "btt"})
_BOOKMARK_UPDATE_FIELDS = frozenset(
    {
        "page",
        "finished",
        "fit_to",
        "two_pages",
        "reading_direction",
    }
)
_COMIC_ONLY_FIELDS = ("pk", "page_count")


class BookmarkBaseView(AuthFilterGenericAPIView):
    """Bookmark Updater."""

    def get_bookmark_search_kwargs(self, comic_filter=None):
        """Get the search kwargs for a user's authentication state."""
        search_kwargs = {}

        if comic_filter:
            for key, value in comic_filter.items():
                search_kwargs[f"comic__{key}"] = value

        if self.request.user.is_authenticated:
            search_kwargs["user"] = self.request.user
        else:
            if not self.request.session or not self.request.session.session_key:
                LOG.debug("no session, make one")
                self.request.session.save()
            search_kwargs["session_id"] = self.request.session.session_key
        return search_kwargs

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
        if (
            rd in VERTICAL_READING_DIRECTIONS
            or bm.reading_direction in VERTICAL_READING_DIRECTIONS
            and bm.two_pages
        ):
            updates["two_pages"] = None

    def notify_library_changed(self):
        """Notify one user that their library changed."""
        if user := self.request.user:
            uid = user.id  # type: ignore
        else:
            uid = self.request.session.session_key
        group = f"user_{uid}"
        task = NotifierTask("LIBRARY_CHANGED", group)
        LIBRARIAN_QUEUE.put(task)

    def _update_bookmarks(self, search_kwargs, updates):
        """Update existing bookmarks."""
        count = 0
        finished = False
        if not updates:
            return count, finished
        group_acl_filter = self.get_group_acl_filter(Bookmark)
        update_fields = set(updates.keys()) & _BOOKMARK_UPDATE_FIELDS
        update_fields.add("updated_at")
        only_fields = (*update_fields, "pk")
        existing_bookmarks = Bookmark.objects.filter(group_acl_filter).filter(
            **search_kwargs
        )
        if updates.get("page") is not None:
            existing_bookmarks = existing_bookmarks.annotate(
                page_count=F("comic__page_count")
            )
        existing_bookmarks = existing_bookmarks.only(*only_fields)
        update_bookmarks = []
        for bm in existing_bookmarks:
            self._update_bookmarks_validate_page(bm, updates)
            self._update_bookmarks_validate_two_pages(bm, updates)
            old_finished = bm.finished
            for key, value in updates.items():
                setattr(bm, key, value)
            bm.updated_at = Now()
            update_bookmarks.append(bm)
            finished = finished or old_finished != bm.finished
        count = len(update_bookmarks)
        if count:
            Bookmark.objects.bulk_update(update_bookmarks, tuple(update_fields))
        return count, finished
        # LOG.debug(f"Updated {count} bookmarks.")

    @staticmethod
    def _create_bookmarks_validate_two_pages(updates):
        """Force vertical view to not use two pages."""
        if (
            updates.get("two_pages")
            and updates.get("reading_direction") in VERTICAL_READING_DIRECTIONS
        ):
            updates.pop("two_pages", None)

    def _create_bookmarks(self, comic_filter, search_kwargs, updates):
        """Create new bookmarks for comics that don't exist yet."""
        count = 0
        finished = False
        self._create_bookmarks_validate_two_pages(updates)
        if not updates:
            return count, finished
        create_bookmarks = []
        group_acl_filter = self.get_group_acl_filter(Comic)
        exclude = {}
        for key, value in search_kwargs.items():
            exclude["bookmark__" + key] = value
        create_bookmark_comics = (
            Comic.objects.filter(group_acl_filter)
            .filter(**comic_filter)
            .exclude(**exclude)
            .only(*_COMIC_ONLY_FIELDS)
        )
        finished = False
        for comic in create_bookmark_comics:
            defaults = {"comic": comic}
            defaults.update(updates)
            for key, value in search_kwargs.items():
                if not key.startswith("comic"):
                    defaults[key] = value

            bm = Bookmark(**defaults)
            create_bookmarks.append(bm)
        count = len(create_bookmarks)
        if count:
            Bookmark.objects.bulk_create(
                create_bookmarks,
                update_fields=tuple(_BOOKMARK_UPDATE_FIELDS),
                unique_fields=Bookmark._meta.unique_together[0],  # type: ignore
            )
            finished = updates.get("finished", False)
            # LOG.debug(f"Create {count} bookmarks.")
        return count, finished

    def update_bookmarks(self, updates, comic_filter):
        """Update a user bookmark."""
        search_kwargs = self.get_bookmark_search_kwargs(comic_filter)
        count, finished = self._update_bookmarks(search_kwargs, updates)
        create_count, create_finished = self._create_bookmarks(
            comic_filter, search_kwargs, updates
        )
        count += create_count
        finished = finished or create_finished
        if count and finished:
            self.notify_library_changed()


class BookmarkView(BookmarkBaseView):
    """User Bookmark View."""

    serializer_class = BookmarkSerializer

    def _parse_params(self):
        """Validate and translate the submitted data."""
        group = self.kwargs.get("group")
        # If the target is recursive, strip everything but finished state data.
        serializer_class = None if group == "c" else BookmarkFinishedSerializer

        data = self.request.data  # type: ignore
        if serializer_class:
            serializer = serializer_class(data=data, partial=True)
        else:
            serializer = self.get_serializer(data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @extend_schema(request=serializer_class, responses=None)
    def patch(self, *_args, **_kwargs):
        """Update bookmarks recursively."""
        updates = self._parse_params()

        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        rel = "folders__in" if group == FOLDER_GROUP else GROUP_RELATION[group] + "__in"
        comic_filter = {rel: pks}

        self.update_bookmarks(updates, comic_filter)
        return Response()
