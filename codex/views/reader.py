"""Views for reading comic books."""
from logging import getLogger

from comicbox.comic_archive import ComicArchive
from django.http import HttpResponse
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from codex.models import Comic
from codex.serializers.reader import ComicReaderInfoSerializer
from codex.serializers.redirect import ReaderRedirectSerializer
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.session import SessionView


LOG = getLogger(__name__)


class ComicOpenedView(SessionView):
    """Get info for displaying comic pages."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    def _get_prev_next_comics(self):
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

        return current_comic, routes

    def get(self, request, *args, **kwargs):
        """Get method."""
        # Get the preve next links and the comic itself in the same go
        comic, routes = self._get_prev_next_comics()
        browser_route = self.get_session(self.BROWSER_KEY).get("route")

        if not comic:
            pk = self.kwargs.get("pk")
            detail = {
                "route": browser_route,
                "reason": f"comic {pk} not found",
                "serializer": ReaderRedirectSerializer,  # type: ignore
            }
            raise NotFound(detail=detail)
        data = {
            "title": {
                "seriesName": comic.series.name,
                "volumeName": comic.volume.name,
                "issue": comic.issue,
                "issueCount": comic.volume.issue_count,
            },
            "maxPage": comic.max_page,
            "routes": routes,
            "browserRoute": browser_route,
        }
        serializer = ComicReaderInfoSerializer(data)
        return Response(serializer.data)


class ComicPageView(APIView):
    """Display a comic page from the archive itself."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

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
            LOG.warning(exc)
            raise NotFound(detail="comic page not found") from exc
