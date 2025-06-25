"""Extract metadata from comic archive."""

from datetime import datetime
from tarfile import TarError
from zipfile import BadZipFile, LargeZipFile

from comicbox.box import Comicbox
from comicbox.exceptions import UnsupportedArchiveTypeError
from py7zr.exceptions import ArchiveError as Py7zError
from rarfile import Error as RarError

from codex.choices.admin import AdminFlagChoices
from codex.librarian.scribe.importer.const import EXTRACTED, FIS, SKIPPED
from codex.librarian.scribe.importer.read.aggregate_path import (
    AggregateMetadataImporter,
)
from codex.librarian.scribe.importer.status import ImporterStatusTypes
from codex.librarian.status import Status
from codex.models.admin import AdminFlag
from codex.models.comic import Comic
from codex.settings import COMICBOX_CONFIG


class ExtractMetadataImporter(AggregateMetadataImporter):
    """Aggregate metadata from comics to prepare for importing."""

    @staticmethod
    def _metadata_mtime(path: str) -> datetime | None:
        try:
            comic = Comic.objects.get(path=path)
        except Comic.DoesNotExist:
            return None
        return comic.metadata_mtime

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

    def _extract_path(self, path: str, *, import_metadata: bool):
        """Extract metadata from comic and clean it for codex."""
        md = {}
        failed_import = {}
        try:
            if import_metadata:
                with Comicbox(path, config=COMICBOX_CONFIG, logger=self.log) as cb:
                    new_md_mtime = cb.get_metadata_mtime()
                    if self.task.check_metadata_mtime:
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
        status = Status(ImporterStatusTypes.READ_TAGS, 0, total_paths)
        try:
            if not total_paths:
                return count

            self.log.info(
                f"Reading tags from {total_paths} comics in {self.library.path}..."
            )
            self.status_controller.start(status, notify=True)

            # Set import_metadata flag
            import_metadata = self._set_import_metadata_flag()

            for path in all_paths:
                if md := self._extract_path(path, import_metadata=import_metadata):
                    self.metadata[EXTRACTED][path] = md
                else:
                    self.metadata[SKIPPED].add(path)

                status.increment_complete()
                self.status_controller.update(status)

            skipped_count = len(self.metadata[SKIPPED])
            count = total_paths - skipped_count
            level = "INFO" if count else "DEBUG"
            self.log.log(level, f"Read metadata from {count} comics.")
            level = "INFO" if skipped_count else "DEBUG"
            self.log.log(
                level,
                f"Skipped {skipped_count} comics because metadata appears unchanged.",
            )
        finally:
            self.metadata.pop(SKIPPED)
            self.status_controller.finish(status)
        return count

    def read(self):
        """Extract and aggregate metadata."""
        self.extract_metadata()
        self.aggregate_metadata()
