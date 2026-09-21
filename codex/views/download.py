"""Download a comic archive."""

from pathlib import Path
from typing import IO

from django.http import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from loguru import logger

from codex.models.comic import Comic
from codex.views.auth import AuthFilterAPIView


class DownloadView(AuthFilterAPIView):
    """Return the comic archive file as an attachment."""

    content_type = "application/vnd.comicbook+zip"

    AS_ATTACHMENT: bool = True

    @staticmethod
    def _open_comic_file(pk, path: str) -> IO[bytes]:
        """
        Open the archive, or 404.

        A row whose file is missing or unreadable is a Not Found, not a
        server error: the library is fine, this one file cannot be served
        right now. ``OSError`` only -- a broad catch would turn a real
        programming error into a silent 404. The error text names the
        library path, so it goes to the log and not to the client.
        """
        try:
            # FileResponse requires file handle not be closed in this method.
            return Path(path).open("rb")
        except OSError as err:
            logger.warning(f"Could not open comic {pk} for download: {err!r}")
            reason = f"Comic {pk} file could not be read."
            raise Http404(reason) from err

    @extend_schema(responses={(200, content_type): OpenApiTypes.BINARY})
    def get(self, *_args, **kwargs) -> FileResponse:
        """Download a comic archive."""
        pk = kwargs.get("pk")
        try:
            acl_filter = self.get_acl_filter(Comic, self.request.user)
            comic = (
                Comic.objects.filter(acl_filter)
                .distinct()
                .only("path", "file_type")
                .get(pk=pk)
            )
        except Comic.DoesNotExist as err:
            reason = f"Comic {pk} not not found."
            raise Http404(reason) from err

        comic_file = self._open_comic_file(pk, comic.path)
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
            as_attachment=self.AS_ATTACHMENT,
            content_type=content_type,
            filename=filename,
        )


class FileView(DownloadView):
    """View a single comic in the browser."""

    AS_ATTACHMENT: bool = False
