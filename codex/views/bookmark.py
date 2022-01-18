"""Bookmark views."""
from logging import getLogger

from rest_framework.response import Response
from rest_framework.views import APIView
from stringcase import camelcase, snakecase

from codex.models import Comic, UserBookmark
from codex.serializers.bookmark import (
    ComicReaderBothSettingsSerializer,
    ComicReaderSettingsSerializer,
    UserBookmarkFinishedSerializer,
)
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser_base import BrowserBaseView
from codex.views.session import SessionView


LOG = getLogger(__name__)


class UserBookmarkUpdateMixin(APIView):
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
            if not self.request.session or self.request.session.session_key:
                LOG.verbose("no session, make one")  # type: ignore
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

    @classmethod
    def _create_user_bookmarks(
        cls, existing_comic_pks, comic_filter, search_kwargs, updates
    ):
        """Create new bookmarks for comics that don't exist yet."""
        create_bookmarks = []
        create_bookmark_comics = (
            Comic.objects.filter(**comic_filter)
            .exclude(pk__in=existing_comic_pks)
            .only(*cls._COMIC_ONLY_FIELDS)
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

    def update_one_user_bookmark(self, snake_dict):
        """Update one comic's userbookmark."""
        pk = self.kwargs.get("pk")
        comic_filter = {"pk": pk}
        self.update_user_bookmarks(snake_dict, comic_filter)
        return Response()


class UserBookmarkFinishedView(BrowserBaseView, UserBookmarkUpdateMixin):
    """Mark read or unread recursively."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    def patch(self, request, *args, **kwargs):
        """Mark read or unread recursively."""
        serializer = UserBookmarkFinishedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group = self.kwargs.get("group")
        relation = str(self.GROUP_RELATION.get(group))
        updates = {"finished": serializer.validated_data.get("finished")}

        pk = self.kwargs.get("pk")
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
        "fitTo": None,
        "twoPages": None,
    }
    _SETTINGS_KEYS = ("fit_to", "two_pages")

    def _validate(self, serializer):
        """Validate and translate the submitted data."""
        serializer.is_valid(raise_exception=True)
        # camel 2 snake
        snake_dict = {}
        for key, val in serializer.validated_data.items():
            snake_key = snakecase(key)
            snake_dict[snake_key] = val
        return snake_dict

    def patch(self, request, *args, **kwargs):
        """Patch the bookmark settings for one comic."""
        serializer = ComicReaderSettingsSerializer(data=self.request.data)
        snake_dict = self._validate(serializer)
        return self.update_one_user_bookmark(snake_dict)

    def put(self, request, *args, **kwargs):
        """Put the session settings for all comics."""
        serializer = ComicReaderSettingsSerializer(data=self.request.data)
        snake_dict = self._validate(serializer)
        # Default for all comics
        params = {"defaults": snake_dict}
        self.save_session(params)

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
        defaults = self.get_session()["defaults"]
        ub = self._get_user_bookmark()

        # Load settings into global and local parts
        data = {"globl": {}, "local": {}}
        for key in self._SETTINGS_KEYS:
            camel_key = camelcase(key)
            data["globl"][camel_key] = defaults.get(key)
            if ub:
                val = getattr(ub, key)
            else:
                val = None
            data["local"][camel_key] = val

        serializer = ComicReaderBothSettingsSerializer(data)

        return Response(serializer.data)
