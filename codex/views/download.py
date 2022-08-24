"""Download a comic archive."""

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

    @extend_schema(responses={(200, content_type): OpenApiTypes.BINARY})
    def get(self, request, *args, **kwargs):
        """Download a comic archive."""
        pk = kwargs.get("pk")
        try:
            group_acl_filter = self.get_group_acl_filter(True)
            comic_path = (
                Comic.objects.filter(group_acl_filter).only("path").get(pk=pk).path
            )
        except Comic.DoesNotExist as err:
            raise Http404(f"Comic {pk} not not found.") from err

        fd = open(comic_path, "rb")
        return FileResponse(fd, as_attachment=True, content_type=self.content_type)
