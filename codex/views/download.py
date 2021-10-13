"""Download a comic archive."""

from django.http import FileResponse, Http404
from rest_framework.views import APIView

from codex.models import Comic
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers


class ComicDownloadView(APIView):
    """Return the comic archive file as an attachment."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    def get(self, request, *args, **kwargs):
        """Download a comic archive."""
        pk = kwargs.get("pk")
        try:
            comic_path = Comic.objects.only("path").get(pk=pk).path
        except Comic.DoesNotExist as err:
            raise Http404(f"Comic {pk} not not found.") from err

        fd = open(comic_path, "rb")
        return FileResponse(fd, as_attachment=True)
