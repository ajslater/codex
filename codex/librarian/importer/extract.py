"""Extract metadata from comic archive."""

from datetime import datetime
from tarfile import TarError
from zipfile import BadZipFile, LargeZipFile

from comicbox.box import Comicbox
from comicbox.config import get_config
from comicbox.exceptions import UnsupportedArchiveTypeError
from comicbox.schemas.comicbox import (
    COVER_DATE_KEY,
    DATE_KEY,
    NUMBER_KEY,
    STORE_DATE_KEY,
    STORIES_KEY,
    SUFFIX_KEY,
)
from py7zr.exceptions import ArchiveError as Py7zError
from rarfile import Error as RarError

from codex.librarian.importer.const import FIS
from codex.librarian.importer.query_fks import QueryForeignKeysImporter
from codex.models.comic import Comic
from codex.settings import LOGLEVEL

_COMICBOX_CONFIG = get_config(
    {
        "compute_pages": False,
        "loglevel": LOGLEVEL,
    }
)
_UNUSED_COMICBOX_FIELDS = (
    "alternate_images",
    "bookmark",
    "credit_primaries",
    "ext",
    "manga",
    "pages",
    "prices",  # add
    "protagonist",  # add
    "remainders",
    "reprints",  # add
    "universes",  # add
    "updated_at",
)


class ExtractMetadataImporter(QueryForeignKeysImporter):
    """Aggregate metadata from comics to prepare for importing."""

    @staticmethod
    def _extract_clean_md(md):
        for key in _UNUSED_COMICBOX_FIELDS:
            md.pop(key, None)

    @staticmethod
    def _extract_transform(md):
        if date := md.pop(DATE_KEY, None):
            date.pop(COVER_DATE_KEY, None)
            date.pop(STORE_DATE_KEY, None)
            md.update(date)

        if issue := md.pop("issue", None):
            if number := issue.pop(NUMBER_KEY, None):
                md["issue_number"] = number
            if suffix := issue.pop(SUFFIX_KEY, None):
                md["issue_suffix"] = suffix

        if stories := md.pop(STORIES_KEY, None):
            md["name"] = "; ".join(stories)

    @staticmethod
    def _metadata_mtime(path: str) -> datetime | None:
        try:
            comic = Comic.objects.get(path=path)
        except Comic.DoesNotExist:
            return None
        return comic.metadata_mtime

    def extract(self, path: str, *, import_metadata: bool):
        """Extract metadata from comic and clean it for codex."""
        md = {}
        failed_import = {}
        try:
            if import_metadata:
                with Comicbox(path, config=_COMICBOX_CONFIG) as cb:
                    new_md_mtime = cb.get_metadata_mtime()
                    if not self.task.force_import_metadata:
                        old_md_mtime = self._metadata_mtime(path)
                        if (
                            old_md_mtime
                            and new_md_mtime
                            and new_md_mtime <= old_md_mtime
                        ):
                            return md
                    md = cb.to_dict()
                    md = md.get("comicbox", {})
                    md["file_type"] = cb.get_file_type()
                    md["metadata_mtime"] = new_md_mtime
            md["path"] = path
            self._extract_clean_md(md)
            self._extract_transform(md)
        except (
            UnsupportedArchiveTypeError,
            BadZipFile,
            LargeZipFile,
            RarError,
            Py7zError,
            TarError,
            OSError,
        ) as exc:
            self.log.warning(f"Failed to import {path}: {exc}")
            failed_import = {path: exc}
        except Exception as exc:
            self.log.exception(f"Failed to import: {path}")
            failed_import = {path: exc}
        if failed_import:
            self.metadata[FIS].update(failed_import)
        return md
