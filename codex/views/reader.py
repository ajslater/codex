"""Views for reading comic books."""
from comicbox.comic_archive import ComicArchive
from django.db.models import F
from django.http import HttpResponse
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from codex.models import Comic
from codex.pdf import PDF
from codex.serializers.reader import ComicReaderInfoSerializer
from codex.serializers.redirect import ReaderRedirectSerializer
from codex.settings.logging import get_logger
from codex.version import COMICBOX_CONFIG
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.group_filter import GroupACLMixin
from codex.views.session import SessionView


LOG = get_logger(__name__)


class ComicOpenedView(SessionView, GroupACLMixin):
    """Get info for displaying comic pages."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]
    SESSION_KEY = SessionView.READER_KEY

    def _get_prev_next_comics(self):
        """
        Get the previous and next comics in a series.

        Uses iteration in python. There are some complicated ways of
        doing this with __gt[0] & __lt[0] in the db, but I think they
        might be even more expensive.
        """
        pk = self.kwargs.get("pk")
        group_acl_filter = self.get_group_acl_filter(True)
        comics = (
            Comic.objects.filter(group_acl_filter)
            .filter(series__comic=pk)
            .annotate(
                series_name=F("series__name"),
                volume_name=F("volume__name"),
                issue_count=F("volume__issue_count"),
            )
            .order_by(*Comic.ORDERING)
            .values(
                "pk",
                "file_format",
                "issue",
                "issue_count",
                "issue_suffix",
                "max_page",
                "series_name",
                "volume_name",
            )
        )

        current_comic = None
        prev_route = next_route = None
        for comic in comics:
            if current_comic is not None:
                next_route = {"pk": comic["pk"], "page": 0}
                break
            elif comic["pk"] == pk:
                current_comic = comic
            else:
                # Haven't matched yet, so set the previous comic
                prev_route = {"pk": comic["pk"], "page": comic["max_page"]}
        routes = {"prev_book": prev_route, "next_book": next_route}

        return current_comic, routes

    def get(self, request, *args, **kwargs):
        """Get method."""
        # Get the preve next links and the comic itself in the same go
        comic, routes = self._get_prev_next_comics()
        browser_route = self.get_from_session(
            "route", session_key=SessionView.BROWSER_KEY
        )

        if not comic:
            pk = self.kwargs.get("pk")
            detail = {
                "route": browser_route,
                "reason": f"comic {pk} not found",
                "serializer": ReaderRedirectSerializer,
            }
            raise NotFound(detail=detail)
        data = {
            "comic": comic,
            "routes": routes,
            "browser_route": browser_route,
        }
        serializer = ComicReaderInfoSerializer(data)
        return Response(serializer.data)


class ComicPageView(APIView, GroupACLMixin):
    """Display a comic page from the archive itself."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]
    SESSION_KEY = SessionView.READER_KEY

    def get(self, request, *args, **kwargs):
        """Get the comic page from the archive."""
        pk = self.kwargs.get("pk")
        comic = None
        try:
            group_acl_filter = self.get_group_acl_filter(True)
            comic = Comic.objects.filter(group_acl_filter).only("path").get(pk=pk)
            page = self.kwargs.get("page")
            if comic.file_format == Comic.FileFormats.PDF:
                car = PDF(comic.path)
                content_type = PDF.MIME_TYPE
            else:
                car = ComicArchive(comic.path, config=COMICBOX_CONFIG)
                content_type = "image/jpeg"
            page_image = car.get_page_by_index(page)
            return HttpResponse(page_image, content_type=content_type)
        except Comic.DoesNotExist as exc:
            raise NotFound(detail=f"comic {pk} not found in db.") from exc
        except FileNotFoundError as exc:
            if comic:
                path = comic.path
            else:
                path = f"path for {pk}"
            raise NotFound(detail=f"comic {path} not found.") from exc
        except Exception as exc:
            LOG.warning(exc)
            raise NotFound(detail="comic page not found") from exc
