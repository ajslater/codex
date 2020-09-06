"""View for marking comics read and unread."""
import logging

from django.db.models import F
from django.db.models import FilteredRelation
from django.http import FileResponse
from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from codex.models import Comic
from codex.serializers.metadata import ComicSerializer
from codex.serializers.metadata import UserBookmarkFinishedSerializer
from codex.views.browser import BrowseView
from codex.views.mixins import SessionMixin
from codex.views.mixins import UserBookmarkMixin


LOG = logging.getLogger(__name__)


class ComicDownloadView(APIView):
    """Return the comic archive file as an attachment."""

    def get(self, request, *args, **kwargs):
        """Download a comic archive."""
        pk = kwargs.get("pk")
        try:
            comic_path = Comic.objects.only("path").get(pk=pk).path
        except Comic.DoesNotExist:
            raise Http404(f"Comic {pk} not not found.")

        fd = open(comic_path, "rb")
        return FileResponse(fd, as_attachment=True)


class UserBookmarkFinishedView(APIView, SessionMixin, UserBookmarkMixin):
    """Mark read or unread recursively."""

    def patch(self, request, *args, **kwargs):
        """Mark read or unread recursively."""
        browse_type = self.kwargs.get("browse_type")
        pk = self.kwargs.get("pk")

        serializer = UserBookmarkFinishedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        relation = BrowseView.GROUP_RELATION.get(browse_type)
        comics = Comic.objects.filter(**{relation: pk}).only("pk")
        updates = {"finished": serializer.validated_data.get("finished")}

        for comic in comics:
            # can't do this in bulk if using update_or_create
            self.update_user_bookmark(updates, comic=comic)

        return Response()


class ComicMetadataView(APIView, SessionMixin, UserBookmarkMixin):
    """Comic metadata."""

    queryset = Comic.objects.all()

    def get(self, request, *args, **kwargs):
        """Get metadata for a single comic."""
        # This filtered relation is simpler than filtering on every relation
        comic = Comic.objects
        ub_filter = self.get_userbookmark_filter(True)
        comic = comic.annotate(
            my_bookmark=FilteredRelation("userbookmark", condition=ub_filter),
            fit_to=F("my_bookmark__fit_to"),
            two_pages=F("my_bookmark__two_pages"),
            finished=F("my_bookmark__finished"),
            bookmark=F("my_bookmark__bookmark"),
            publisher_name=F("publisher__name"),
            imprint_name=F("imprint__name"),
            series_name=F("series__name"),
            volume_count=F("series__volume_count"),
            volume_name=F("volume__name"),
            issue_count=F("volume__issue_count"),
            x_page_count=F("page_count"),
        )

        # Annotate progress
        comic = self.annotate_progress(comic)

        pk = kwargs.get("pk")
        res = comic.select_related().prefetch_related().get(pk=pk)
        serializer = ComicSerializer(res)
        return Response(serializer.data)
