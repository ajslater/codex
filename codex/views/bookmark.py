"""Bookmark views."""
from rest_framework.response import Response
from rest_framework.views import APIView

from codex.models import Comic, UserBookmark
from codex.serializers.bookmark import (
    ComicReaderBothSettingsSerializer,
    ComicReaderSettingsSerializer,
    UserBookmarkFinishedSerializer,
)
from codex.settings.logging import get_logger
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser_base import BrowserBaseView
from codex.views.group_filter import GroupACLMixin
from codex.views.session import SessionView


LOG = get_logger(__name__)


class UserBookmarkUpdateMixin(APIView, GroupACLMixin):
    """UserBookmark Updater."""

    _USERBOOKMARK_UPDATE_FIELDS = ["bookmark", "finished", "fit_to", "two_pages"]
    _USERBOOKMARK_ONLY_FIELDS = _USERBOOKMARK_UPDATE_FIELDS + ["pk", "comic"]
    _COMIC_ONLY_FIELDS = ("pk", "max_page")

    def get_user_bookmark_search_kwargs(self, comic_filter):
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

    @classmethod
    def _update_user_bookmarks(cls, search_kwargs, updates):
        """Update existing bookmarks."""
        existing_bookmarks = (
            UserBookmark.objects.filter(**search_kwargs)
            .select_related("comic")
            .only(*cls._USERBOOKMARK_ONLY_FIELDS)
        )
        update_bookmarks = []
        existing_comic_pks = set()
        for ub in existing_bookmarks:
            if updates.get("bookmark") == ub.comic.max_page:
                # Auto finish on bookmark last page
                ub.finished = True

            for key, value in updates.items():
                setattr(ub, key, value)
            update_bookmarks.append(ub)
            existing_comic_pks.add(ub.comic.pk)
        UserBookmark.objects.bulk_update(
            update_bookmarks, cls._USERBOOKMARK_UPDATE_FIELDS
        )
        return existing_comic_pks

    def _create_user_bookmarks(
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

            ub = UserBookmark(**defaults)
            if updates.get("bookmark") == comic.max_page:
                # Auto finish on bookmark last page
                # This almost never happens. Possibly never.
                ub.finished = True
            create_bookmarks.append(ub)
        UserBookmark.objects.bulk_create(create_bookmarks)

    def update_user_bookmarks(self, updates, comic_filter):
        """Update a user bookmark."""
        search_kwargs = self.get_user_bookmark_search_kwargs(comic_filter)
        existing_comic_pks = self._update_user_bookmarks(search_kwargs, updates)
        self._create_user_bookmarks(
            existing_comic_pks, comic_filter, search_kwargs, updates
        )

    def update_one_user_bookmark(self, updates):
        """Update one comic's userbookmark."""
        pk = self.kwargs.get("pk")
        comic_filter = {"pk": pk}
        self.update_user_bookmarks(updates, comic_filter)
        return Response()


class UserBookmarkFinishedView(BrowserBaseView, UserBookmarkUpdateMixin):
    """Mark read or unread recursively."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    def patch(self, request, *args, **kwargs):
        """Mark read or unread recursively."""
        serializer = UserBookmarkFinishedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updates = {"finished": serializer.validated_data.get("finished")}

        group = self.kwargs.get("group")
        pk = self.kwargs.get("pk")
        if group == "f":
            comic_filter = {"folders__in": [pk]}
        else:
            relation = self.GROUP_RELATION.get(group)
            comic_filter = {relation: pk}
        self.update_user_bookmarks(updates, comic_filter=comic_filter)
        return Response()


class ComicBookmarkView(UserBookmarkUpdateMixin):
    """Bookmark updater."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    def patch(self, request, *args, **kwargs):
        """Save a user bookmark after a page change."""
        page = self.kwargs.get("page")
        updates = {"bookmark": page}
        return self.update_one_user_bookmark(updates)


class ComicSettingsView(SessionView, UserBookmarkUpdateMixin):
    """Set Comic Settigns."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    SESSION_KEY = SessionView.READER_KEY
    _NULL_READER_SETTINGS = {
        "fit_to": None,
        "two_pages": None,
    }
    _SETTINGS_KEYS = ("fit_to", "two_pages")

    def _validate(self):
        """Validate and translate the submitted data."""
        serializer = ComicReaderSettingsSerializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def patch(self, request, *args, **kwargs):
        """Patch the bookmark settings for one comic."""
        updates = self._validate()
        return self.update_one_user_bookmark(updates)

    def put(self, request, *args, **kwargs):
        """Put the session settings for all comics."""
        updates = self._validate()
        # Default for all comics
        self.load_params_from_session()
        self.params["display"] = updates
        self.save_params_to_session()

        # Null out this comic's settings so it uses all comic defaults
        return self.update_one_user_bookmark(self._NULL_READER_SETTINGS)

    def _get_user_bookmark(self):
        """Get a user bookmark."""
        pk = self.kwargs.get("pk")
        comic_filter = {"pk": pk}
        search_kwargs = self.get_user_bookmark_search_kwargs(comic_filter)
        try:
            ub = UserBookmark.objects.get(**search_kwargs)
        except UserBookmark.DoesNotExist:
            ub = None
        return ub

    def get(self, request, *args, **kwargs):
        """Get comic settings."""
        defaults = self.get_from_session("display")
        ub = self._get_user_bookmark()

        # Load settings into global and local parts
        data = {"globl": {}, "local": {}}
        for key in self._SETTINGS_KEYS:
            data["globl"][key] = defaults.get(key)
            if ub:
                val = getattr(ub, key)
            else:
                val = None
            data["local"][key] = val

        serializer = ComicReaderBothSettingsSerializer(data)
        return Response(serializer.data)
