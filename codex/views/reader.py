"""Views for reading comic books."""
from logging import getLogger

from comicbox.comic_archive import ComicArchive
from django.http import HttpResponse
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView
from stringcase import camelcase

from codex.models import Comic
from codex.serializers.reader import ComicReaderInfoSerializer
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.mixins import SessionMixin, UserBookmarkMixin


LOG = getLogger(__name__)


class ComicOpenedView(SessionMixin, UserBookmarkMixin):
    """Get info for displaying comic pages."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]
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
                next_route = {"pk": comic.pk, "page": 0}
                break
            elif comic.pk == pk:
                current_comic = comic
            else:
                # Haven't matched yet, so set the previous comic
                prev_route = {"pk": comic.pk, "page": comic.max_page}
        routes = {"prevBook": prev_route, "nextBook": next_route}

        if current_comic is None:
            raise ValueError(f"Comic for {pk} not found.")

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
        comic = None
        try:
            comic = Comic.objects.only("path").get(pk=pk)
            car = ComicArchive(comic.path)
            page = self.kwargs.get("page")
            page_image = car.get_page_by_index(page)
            return HttpResponse(page_image, content_type="image/jpeg")
        except Comic.DoesNotExist as exc:
            raise NotFound(detail=f"comic {pk} not found in db.") from exc
        except FileNotFoundError as exc:
            if comic:
                path = comic.path
            else:
                path = f"path for {pk}"
            raise NotFound(detail=f"comic {path} not found.") from exc
        except Exception as exc:
            LOG.exception(exc)
            raise NotFound(detail="comic page not found") from exc
