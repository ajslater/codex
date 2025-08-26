"""Extract metadata from comic archive."""

from datetime import datetime, timezone
from tarfile import TarError
from types import MappingProxyType
from zipfile import BadZipFile, LargeZipFile

from comicbox.box import Comicbox
from comicbox.exceptions import UnsupportedArchiveTypeError
from comicbox.schemas.comicbox import PAGE_COUNT_KEY
from py7zr.exceptions import ArchiveError as Py7zError
from rarfile import Error as RarError

from codex.choices.admin import AdminFlagChoices
from codex.librarian.scribe.importer.const import EXTRACTED, FIS, SKIPPED
from codex.librarian.scribe.importer.read.aggregate_path import (
    AggregateMetadataImporter,
)
from codex.librarian.scribe.importer.statii.read import ImporterReadComicsStatus
from codex.models.admin import AdminFlag
from codex.models.comic import Comic
from codex.settings import COMICBOX_CONFIG


class ExtractMetadataImporter(AggregateMetadataImporter):
    """Aggregate metadata from comics to prepare for importing."""

    @staticmethod
    def _old_comic_values(
        old_comic_values: MappingProxyType, path: str
    ) -> tuple[str | None, int | None, datetime | None]:
        old_comic = old_comic_values.get(path, {})
        old_file_type = old_comic.get("file_type")
        old_page_count = old_comic.get(PAGE_COUNT_KEY)
        old_mtime = old_comic.get("metadata_mtime")
        if old_mtime and (
            old_mtime.tzinfo is None or old_mtime.tzinfo.utcoffset(old_mtime) is None
        ):
            old_mtime = old_mtime.replace(tzinfo=timezone.utc)
        return old_file_type, old_page_count, old_mtime

    def _set_import_metadata_flag(self):
        """Set import_metadata flag."""
        if self.task.force_import_metadata:
            import_metadata = True
        else:
            key = AdminFlagChoices.IMPORT_METADATA.value
            import_metadata = AdminFlag.objects.only("on").get(key=key).on
        if not import_metadata:
            self.log.warning("Admin flag set to NOT import metadata.")
        return import_metadata

    def _extract_path_comicbox(
        self,
        path: str,
        old_comic_values: MappingProxyType,
        *,
        import_metadata: bool,
    ):
        old_file_type, old_page_count, old_mtime = self._old_comic_values(
            old_comic_values, path
        )
        md = {}
        with Comicbox(path, config=COMICBOX_CONFIG, logger=self.log) as cb:
            if import_metadata:
                new_md_mtime = cb.get_metadata_mtime()
                if (
                    not self.task.check_metadata_mtime
                    or not new_md_mtime
                    or not old_mtime
                    or (new_md_mtime > old_mtime)
                ):
                    md = cb.to_dict()
                    md = md.get("comicbox", {})
                    md["metadata_mtime"] = new_md_mtime
                else:
                    md["page_count"] = cb.get_page_count()
            else:
                md["page_count"] = cb.get_page_count()
            file_type = cb.get_file_type()

        if old_page_count == md.get("page_count"):
            md.pop("page_count")
        if old_file_type != file_type:
            md["file_type"] = file_type

        if md:
            md["path"] = path
        return md

    def _extract_path(
        self, path: str, old_comic_values: MappingProxyType, *, import_metadata: bool
    ):
        """Extract metadata from comic and clean it for codex."""
        md = {}
        failed_import = {}
        try:
            md = self._extract_path_comicbox(
                path, old_comic_values, import_metadata=import_metadata
            )
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

    @staticmethod
    def _get_all_old_comic_values(all_paths: frozenset[str]):
        """Get some old comic values."""
        old_comics = Comic.objects.filter(path__in=all_paths).values(
            "path", "metadata_mtime", "page_count", "file_type"
        )
        old_comic_values = {}
        for old_comic in old_comics:
            old_path = old_comic.pop("path")
            old_comic_values[old_path] = old_comic
        return MappingProxyType(old_comic_values)

    def extract_metadata(self, status=None) -> int:
        """Extract comic metadata into memory."""
        count = 0
        self.metadata[SKIPPED] = set()
        self.metadata[EXTRACTED] = {}
        self.metadata[FIS] = {}
        all_paths = self.task.files_modified | self.task.files_created
        self.task.files_modified = frozenset()
        self.task.files_created = frozenset()
        total_paths = len(all_paths)
        status = ImporterReadComicsStatus(0, total_paths)
        try:
            if not total_paths:
                return count

            self.log.debug(
                f"Reading tags from {total_paths} comics in {self.library.path}..."
            )
            self.status_controller.start(status, notify=True)

            # Set import_metadata flag
            import_metadata = self._set_import_metadata_flag()
            old_comic_values = self._get_all_old_comic_values(all_paths)

            for path in all_paths:
                if self.abort_event.is_set():
                    return count
                if md := self._extract_path(
                    path, old_comic_values, import_metadata=import_metadata
                ):
                    self.metadata[EXTRACTED][path] = md
                else:
                    self.metadata[SKIPPED].add(path)

                status.increment_complete()
                self.status_controller.update(status)

            skipped_count = len(self.metadata[SKIPPED])
            count = total_paths - skipped_count
            level = "INFO" if skipped_count else "DEBUG"
            self.log.log(
                level,
                f"Skipped {skipped_count} comics because metadata appears unchanged.",
            )
        finally:
            self.metadata.pop(SKIPPED)
            self.status_controller.finish(status)
        return count
