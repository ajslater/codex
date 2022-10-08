"""Bookmark views."""
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from codex.models import Bookmark, Comic
from codex.serializers.models import BookmarkFinishedSerializer, BookmarkSerializer
from codex.settings.logging import get_logger
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.mixins import GroupACLMixin


LOG = get_logger(__name__)


class BookmarkBaseView(GenericAPIView, GroupACLMixin):
    """Bookmark Updater."""

    _BOOKMARK_UPDATE_FIELDS = ["page", "finished", "fit_to", "two_pages"]
    _BOOKMARK_ONLY_FIELDS = _BOOKMARK_UPDATE_FIELDS + ["pk", "comic"]
    _COMIC_ONLY_FIELDS = ("pk", "max_page")

    def get_bookmark_filter(self):
        """Get search kwargs for the reader."""
        search_kwargs = {}
        if self.request.user.is_authenticated:
            search_kwargs["bookmark__user"] = self.request.user
        else:
            if not self.request.session or not self.request.session.session_key:
                LOG.verbose("no session, make one")
                self.request.session.save()
            search_kwargs["bookmark__session_id"] = self.request.session.session_key
        return search_kwargs

    def get_bookmark_search_kwargs(self, comic_filter):
        """Get the search kwargs for a user's authentication state."""
        search_kwargs = {}
        for key, value in comic_filter.items():
            search_kwargs[f"comic__{key}"] = value

        if self.request.user.is_authenticated:
            search_kwargs["user"] = self.request.user
        else:
            if not self.request.session or not self.request.session.session_key:
                LOG.verbose("no session, make one")
                self.request.session.save()
            search_kwargs["session_id"] = self.request.session.session_key
        return search_kwargs

    def _update_bookmarks(self, search_kwargs, updates):
        """Update existing bookmarks."""
        group_acl_filter = self.get_group_acl_filter(False)
        existing_bookmarks = (
            Bookmark.objects.filter(group_acl_filter)
            .filter(**search_kwargs)
            .select_related("comic")
            .only(*self._BOOKMARK_ONLY_FIELDS)
        )
        update_bookmarks = []
        existing_comic_pks = set()
        for bm in existing_bookmarks:
            if updates.get("page") == bm.comic.max_page:
                # Auto finish on bookmark last page
                bm.finished = True

            for key, value in updates.items():
                setattr(bm, key, value)
            update_bookmarks.append(bm)
            existing_comic_pks.add(bm.comic.pk)
        Bookmark.objects.bulk_update(update_bookmarks, self._BOOKMARK_UPDATE_FIELDS)
        return existing_comic_pks

    def _create_bookmarks(
        self, existing_comic_pks, comic_filter, search_kwargs, updates
    ):
        """Create new bookmarks for comics that don't exist yet."""
        create_bookmarks = []
        group_acl_filter = self.get_group_acl_filter(True)
        create_bookmark_comics = (
            Comic.objects.filter(group_acl_filter)
            .filter(**comic_filter)
            .exclude(pk__in=existing_comic_pks)
            .only(*self._COMIC_ONLY_FIELDS)
        )
        for comic in create_bookmark_comics:
            defaults = {"comic": comic}
            defaults.update(updates)
            for key, value in search_kwargs.items():
                if not key.startswith("comic"):
                    defaults[key] = value

            bm = Bookmark(**defaults)
            if updates.get("page") == comic.max_page:
                # Auto finish on bookmark last page
                # This almost never happens. Possibly never.
                bm.finished = True
            create_bookmarks.append(bm)
        Bookmark.objects.bulk_create(create_bookmarks)

    def update_bookmarks(self, updates, comic_filter):
        """Update a user bookmark."""
        search_kwargs = self.get_bookmark_search_kwargs(comic_filter)
        existing_comic_pks = self._update_bookmarks(search_kwargs, updates)
        self._create_bookmarks(existing_comic_pks, comic_filter, search_kwargs, updates)


class BookmarkView(BookmarkBaseView):
    """User Bookmark View."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]
    serializer_class = BookmarkSerializer

    def _validate(self, serializer_class):
        """Validate and translate the submitted data."""
        data = self.request.data
        if serializer_class:
            serializer = serializer_class(data=data)
        else:
            serializer = self.get_serializer(data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @extend_schema(request=serializer_class, responses=None)
    def patch(self, request, *args, **kwargs):
        """Update bookmarks recursively."""
        group = self.kwargs.get("group")
        if group == "c":
            serializer_class = None
        else:
            # If the target is recursive, strip everything but finished state data.
            serializer_class = BookmarkFinishedSerializer

        try:
            updates = self._validate(serializer_class)
        except Exception as exc:
            LOG.error(exc)
            raise exc

        pk = self.kwargs.get("pk")
        if group == "f":
            comic_filter = {"folders__in": [pk]}
        else:
            relation = self.GROUP_RELATION.get(group)
            comic_filter = {relation: pk}

        self.update_bookmarks(updates, comic_filter=comic_filter)
        return Response()
