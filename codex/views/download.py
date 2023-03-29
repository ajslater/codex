"""Download a comic archive."""
from pathlib import Path

from django.http import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from codex.models import Comic
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.mixins import GroupACLMixin


class DownloadView(APIView, GroupACLMixin):
    """Return the comic archive file as an attachment."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]
    content_type = "application/vnd.comicbook+zip"

    _DOWNLOAD_SELECT_RELATED = ("series", "volume")
    _DOWNLOAD_FIELDS = ("path", "series", "volume", "issue", "issue_suffix", "name")

    @extend_schema(responses={(200, content_type): OpenApiTypes.BINARY})
    def get(self, *args, **kwargs):
        """Download a comic archive."""
        pk = kwargs.get("pk")
        try:
            group_acl_filter = self.get_group_acl_filter(True)
            comic = (
                Comic.objects.filter(group_acl_filter)
                .select_related(*self._DOWNLOAD_SELECT_RELATED)
                .only(*self._DOWNLOAD_FIELDS)
                .get(pk=pk)
            )
        except Comic.DoesNotExist as err:
            reason = f"Comic {pk} not not found."
            raise Http404(reason) from err

        comic_file = Path(comic.path).open("rb")
        return FileResponse(
            comic_file,
            as_attachment=True,
            content_type=self.content_type,
            filename=comic.filename(),
        )
