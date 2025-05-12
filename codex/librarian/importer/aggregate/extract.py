"""Extract metadata from comic archive."""

from tarfile import TarError
from zipfile import BadZipFile, LargeZipFile

from comicbox.box import Comicbox
from comicbox.config import get_config
from comicbox.exceptions import UnsupportedArchiveTypeError
from comicbox.schemas.comicbox import (
    COVER_DATE_KEY,
    DATE_KEY,
    NAME_KEY,
    NUMBER_KEY,
    STORE_DATE_KEY,
    STORIES_KEY,
    SUFFIX_KEY,
)
from py7zr.exceptions import ArchiveError as Py7zError
from rarfile import Error as RarError

from codex.librarian.importer.const import FIS
from codex.librarian.importer.query_fks import QueryForeignKeysImporter
from codex.settings.settings import LOGLEVEL

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
            if name := issue.pop(NAME_KEY, None):
                issue["issue"] = name
            if number := issue.pop(NUMBER_KEY, None):
                issue["issue_number"] = number
            if suffix := issue.pop(SUFFIX_KEY, None):
                issue["issue_suffix"] = suffix
            md.update(issue)

        if stories := md.pop(STORIES_KEY, None):
            md["name"] = "; ".join(stories)

    def extract(self, path, *, import_metadata: bool):
        """Extract metadata from comic and clean it for codex."""
        md = {}
        failed_import = {}
        try:
            if import_metadata:
                with Comicbox(path, config=_COMICBOX_CONFIG) as cb:
                    md = cb.to_dict()
                    md = md.get("comicbox", {})
                    md["file_type"] = cb.get_file_type()
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
