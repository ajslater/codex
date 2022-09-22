"""Views for reading comic books."""
from django.db.models import F
from django.urls import reverse
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from codex.models import Comic
from codex.serializers.reader import ReaderInfoSerializer
from codex.serializers.redirect import ReaderRedirectSerializer
from codex.settings.logging import get_logger
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.mixins import GroupACLMixin


LOG = get_logger(__name__)
PAGE_TTL = 60 * 60 * 24


class ReaderView(GenericAPIView, GroupACLMixin):
    """Get info for displaying comic pages."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]
    serializer_class = ReaderInfoSerializer

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
        series_index = None
        for index, comic in enumerate(comics):
            if current_comic is not None:
                next_route = {"pk": comic["pk"], "page": 0}
                break
            elif comic["pk"] == pk:
                current_comic = comic
                series_index = index + 1
            else:
                # Haven't matched yet, so set the previous comic
                prev_route = {"pk": comic["pk"], "page": comic["max_page"]}
        routes = {
            "prev_book": prev_route,
            "next_book": next_route,
            "series_index": series_index,
            "series_count": comics.count(),
        }

        return current_comic, routes

    def get_object(self):
        """Get method."""
        # Get the preve next links and the comic itself in the same go
        comic, routes = self._get_prev_next_comics()

        if not comic:
            pk = self.kwargs.get("pk")
            detail = {
                "route": reverse("app:start"),
                "reason": f"comic {pk} not found",
                "serializer": ReaderRedirectSerializer,
            }
            raise NotFound(detail=detail)
        obj = {
            "comic": comic,
            "routes": routes,
        }
        return obj

    def get(self, request, *args, **kwargs):
        """Get the book info."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)
