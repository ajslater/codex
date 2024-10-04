"""Download a comic archive."""

from pathlib import Path

from django.http import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

from codex.models import Comic
from codex.views.auth import AuthFilterAPIView


class DownloadView(AuthFilterAPIView):
    """Return the comic archive file as an attachment."""

    content_type = "application/vnd.comicbook+zip"

    _AS_ATTACHMENT = True

    @extend_schema(responses={(200, content_type): OpenApiTypes.BINARY})
    def get(self, *_args, **kwargs):
        """Download a comic archive."""
        pk = kwargs.get("pk")
        try:
            group_acl_filter = self.get_group_acl_filter(Comic, self.request.user)
            comic = (
                Comic.objects.filter(group_acl_filter)
                .only("path", "file_type")
                .get(pk=pk)
            )
        except Comic.DoesNotExist as err:
            reason = f"Comic {pk} not not found."
            raise Http404(reason) from err

        # FileResponse requires file handle not be closed in this method.
        comic_file = Path(comic.path).open("rb")  # noqa: SIM115
        content_type = "application/"
        if comic.file_type == "PDF":
            content_type += "pdf"
        elif comic.file_type:
            content_type += "vnd.comicbook+" + comic.file_type.lower()
        else:
            content_type += "octet-stream"

        filename = comic.get_filename()
        return FileResponse(
            comic_file,
            as_attachment=self._AS_ATTACHMENT,
            content_type=content_type,
            filename=filename,
        )


class FileView(DownloadView):
    """View a comic in the browser."""

    _AS_ATTACHMENT = False
