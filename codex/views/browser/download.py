"""Download a collection of comics in a zipfile."""

from pathlib import Path
from typing import Final, override

from django.http.response import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from loguru import logger
from zipstream import ZipStream

from codex.views.browser.filters.filter import BrowserFilterView

#: How many comics were left out of the archive because their files
#: could not be read. Absent when every comic made it in.
SKIPPED_HEADER: Final[str] = "X-Codex-Skipped-Comics"


class CollectionDownloadView(BrowserFilterView):
    """Return a collection of comic archives as a streaming zipfile."""

    content_type = "application/zip"
    AS_ATTACHMENT = True
    TARGET: str = "download"

    @override
    def get_object(self) -> tuple[str, ...]:
        """Get comic paths for a browse collection."""
        collection = self.kwargs.get("collection")
        pks = self.kwargs.get("pks")
        if not self.model:
            reason = f"Could not find model for collection {collection}"
            raise Http404(reason)

        try:
            qs = self.get_filtered_queryset(self.model, collection=collection, pks=pks)
            path_rel = self.rel_prefix + "path"
            paths = qs.values_list(path_rel, flat=True)
        except Exception as exc:
            logger.warning(f"Error with download query for {collection}:{pks} {exc}")
            raise

        if not paths:
            reason = f"Comics from {collection}:{pks} not not found."
            raise Http404(reason)

        return tuple(sorted(set(paths)))

    @staticmethod
    def _add_path(zs: ZipStream, path: str) -> bool:
        """
        Queue one comic, or report that its file could not be read.

        Opening and closing the file proves it is readable now.
        ``ZipStream`` only opens each member when the generator reaches
        it, which is long after the 200 and the headers have gone out,
        so an unreadable file discovered then can only truncate the
        archive under a success status. ``OSError`` only, and its text
        names the library path, so it goes to the log and not the client.
        """
        try:
            with Path(path).open("rb"):
                zs.add_path(path)
        except OSError as exc:
            logger.warning(f"Skipped an unreadable comic in a collection zip: {exc!r}")
            return False
        return True

    @classmethod
    def _get_zip_stream(cls, paths: tuple[str, ...]) -> tuple[ZipStream, int]:
        """Build the stream from every readable path, counting the rest."""
        zs = ZipStream(sized=True)
        skipped = 0
        for path in paths:
            if not cls._add_path(zs, path):
                skipped += 1
        if skipped >= len(paths):
            reason = "No comics in this collection could be read."
            raise Http404(reason)
        return zs, skipped

    @extend_schema(responses={(200, content_type): OpenApiTypes.BINARY})
    def get(self, *_args, **kwargs) -> FileResponse:
        """Stream a zip archive of many comics."""
        paths = self.get_object()

        zs, skipped = self._get_zip_stream(paths)
        download_file = zs

        filename = kwargs.get("filename")
        if not filename:
            pks = self.kwargs.get("pks")
            name = self.model.__name__ if self.model else "No Model"
            filename = f"{name} {pks} Comics.zip"

        headers: dict[str, object] = {
            "Content-Length": len(zs),
            "Last-Modified": zs.last_modified,
        }
        if skipped:
            headers[SKIPPED_HEADER] = str(skipped)
        return FileResponse(
            download_file,
            as_attachment=self.AS_ATTACHMENT,
            content_type=self.content_type,
            filename=filename,
            headers=headers,
        )
