"""Download a comic archive."""

from django.http import FileResponse, Http404
from rest_framework.views import APIView

from codex.models import Comic
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.group_filter import GroupACLMixin


class ComicDownloadView(APIView, GroupACLMixin):
    """Return the comic archive file as an attachment."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

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
        return FileResponse(fd, as_attachment=True)
