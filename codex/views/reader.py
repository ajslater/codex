"""Views for reading comic books."""
import logging

from comicbox.comic_archive import ComicArchive
from django.http import HttpResponse
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView
from stringcase import camelcase
from stringcase import snakecase

from codex.models import Comic
from codex.serializers.read import ComicReaderInfoSerializer
from codex.serializers.read import ComicReaderSettingsSerializer
from codex.views.mixins import SessionMixin
from codex.views.mixins import UserBookmarkMixin


LOG = logging.getLogger(__name__)


class ComicOpenedView(APIView, SessionMixin, UserBookmarkMixin):
    """Get info for displaying comic pages."""

    SETTINGS_KEYS = ("fit_to", "two_pages")

    def get_settings(self):
        """Get Settings."""
        reader_session = None
        settings = {"globl": {}, "local": {}}
        reader_session = self.get_session(self.READER_KEY)
        defaults = reader_session.get(
            "defaults", self.SESSION_DEFAULTS[self.READER_KEY]["defaults"]
        )
        pk = self.kwargs.get("pk")
        ub = self.get_user_bookmark(pk)
        for key in self.SETTINGS_KEYS:
            camel_key = camelcase(key)
            settings["globl"][camel_key] = defaults.get(key)
            if ub:
                val = getattr(ub, key)
            else:
                val = None
            settings["local"][camel_key] = val

        return settings

    def get_prev_next_comics(self):
        """
        Get the previous and next comics in a series.

        Uses iteration in python. There are some complicated ways of
        doing this with __gt[0] & __lt[0] in the db, but I think they
        might be even more expensive.
        """
        pk = self.kwargs.get("pk")
        comics = (
            Comic.objects.filter(series__comic=pk)
            .order_by("series__name", "volume__name", "issue")
            .only("pk", "max_page")
        )

        current_comic = None
        prev_route = next_route = None
        for comic in comics:
            if current_comic is not None:
                next_route = {"pk": comic.pk, "pageNumber": 0}
                break
            elif comic.pk == pk:
                current_comic = comic
            else:
                # Haven't matched yet, so set the previous comic
                prev_route = {"pk": comic.pk, "pageNumber": comic.max_page}
        routes = {"prevBook": prev_route, "nextBook": next_route}
        return current_comic, routes

    def get(self, request, *args, **kwargs):
        """Get method."""
        settings = self.get_settings()

        # Get the preve next links and the comic itself in the same go
        comic, routes = self.get_prev_next_comics()

        data = {
            "title": {
                "seriesName": comic.series.name,
                "volumeName": comic.volume.name,
                "issue": comic.issue,
                "issueCount": comic.volume.issue_count,
            },
            "maxPage": comic.max_page,
            "settings": settings,
            "routes": routes,
        }

        serializer = ComicReaderInfoSerializer(data)
        return Response(serializer.data)


class ComicPageView(APIView):
    """Display a comic page from the archive itself."""

    def get(self, request, *args, **kwargs):
        """Get the comic page from the archive."""
        pk = self.kwargs.get("pk")
        comic = Comic.objects.only("path").get(pk=pk)
        try:
            car = ComicArchive(comic.path)
            page_num = self.kwargs.get("page_num")
            page_image = car.get_page_by_index(page_num)
            return HttpResponse(page_image, content_type="image/jpeg")
        except Exception as exc:
            LOG.exception(exc)
            raise NotFound(detail="comic page not found")


class ComicBookmarkView(APIView, UserBookmarkMixin):
    """Bookmark updater."""

    def patch(self, request, *args, **kwargs):
        """Save a user bookmark after a page change."""
        pk = self.kwargs.get("pk")
        page_num = self.kwargs.get("page_num")
        updates = {"bookmark": page_num}
        self.update_user_bookmark(updates, pk=pk)
        return Response()


class ComicSettingsView(APIView, SessionMixin, UserBookmarkMixin):
    """Set Comic Settigns."""

    def validate(self, serializer):
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
        updates = self.validate(serializer)

        pk = self.kwargs.get("pk")
        self.update_user_bookmark(updates, pk=pk)
        return Response()

    def put(self, request, *args, **kwargs):
        """Put the session settings for all comics."""
        serializer = ComicReaderSettingsSerializer(data=self.request.data)
        snake_dict = self.validate(serializer)
        # Default for all comics
        reader_session = self.get_session(self.READER_KEY)
        reader_session["defaults"] = snake_dict
        self.request.session.save()
        return Response()
