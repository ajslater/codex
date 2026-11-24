"""Download a collection of comics in a zipfile."""

from itertools import batched
from pathlib import Path
from typing import Final, override

from django.http.response import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from loguru import logger
from zipstream import ZipStream

from codex.librarian.scribe.readinglists.references import PK_BATCH
from codex.models import ReadingListEntry
from codex.views.browser.filters.filter import BrowserFilterView
from codex.views.const import STORY_ARC_COLLECTION

#: How many comics were left out of the archive because their files
#: could not be read. Absent when every comic made it in.
SKIPPED_HEADER: Final[str] = "X-Codex-Skipped-Comics"
_MIN_POSITION_WIDTH: Final = 3

#: A comic's path and the name it takes in the archive; None keeps its own.
Member = tuple[str, str | None]


def _numbered(paths: list[str]) -> tuple[Member, ...]:
    """Prefix each file with its place, so a sort by name is the order."""
    width = max(_MIN_POSITION_WIDTH, len(str(len(paths))))
    return tuple(
        (path, f"{index:0{width}d} - {Path(path).name}")
        for index, path in enumerate(paths, start=1)
    )


class CollectionDownloadView(BrowserFilterView):
    """Return a collection of comic archives as a streaming zipfile."""

    content_type = "application/zip"
    AS_ATTACHMENT = True
    TARGET: str = "download"

    def _list_members(self, paths: tuple[str, ...]) -> tuple[Member, ...] | None:
        """
        Order one reading list's comics as the list does, numbered.

        Every shown entry is a file, so a comic the list holds twice is in
        the archive twice. Several lists at once keep their own names.
        """
        pks = self.kwargs.get("pks") or ()
        if self.kwargs.get("collection") != STORY_ARC_COLLECTION or len(pks) != 1:
            return None
        rows = sorted(
            row
            for batch in batched(paths, PK_BATCH)
            for row in ReadingListEntry.objects.filter(
                reading_list_id=pks[0], ignored=False, comic__path__in=batch
            ).values_list("position", "pk", "comic__path")
        )
        ordered = [path for _, _, path in rows]
        return _numbered(ordered) if ordered else None

    @override
    def get_object(self) -> tuple[Member, ...]:
        """Get comic paths, and their names in the archive, for a collection."""
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

        unique = tuple(sorted(set(paths)))
        if members := self._list_members(unique):
            return members
        return tuple((path, None) for path in unique)

    @staticmethod
    def _add_path(zs: ZipStream, path: str, arcname: str | None) -> bool:
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
                zs.add_path(path, arcname)
        except OSError as exc:
            logger.warning(f"Skipped an unreadable comic in a collection zip: {exc!r}")
            return False
        return True

    @classmethod
    def _get_zip_stream(cls, members: tuple[Member, ...]) -> tuple[ZipStream, int]:
        """Build the stream from every readable path, counting the rest."""
        zs = ZipStream(sized=True)
        skipped = 0
        for path, arcname in members:
            if not cls._add_path(zs, path, arcname):
                skipped += 1
        if skipped >= len(members):
            reason = "No comics in this collection could be read."
            raise Http404(reason)
        return zs, skipped

    @extend_schema(responses={(200, content_type): OpenApiTypes.BINARY})
    def get(self, *_args, **kwargs) -> FileResponse:
        """Stream a zip archive of many comics."""
        members = self.get_object()

        zs, skipped = self._get_zip_stream(members)
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
