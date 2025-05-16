"""Extract metadata from comic archive."""

from datetime import datetime
from tarfile import TarError
from zipfile import BadZipFile, LargeZipFile

from comicbox.box import Comicbox
from comicbox.exceptions import UnsupportedArchiveTypeError
from py7zr.exceptions import ArchiveError as Py7zError
from rarfile import Error as RarError

from codex.choices.admin import AdminFlagChoices
from codex.librarian.importer.const import EXTRACTED, FIS, SKIPPED
from codex.librarian.importer.query_fks import QueryForeignKeysImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.models.admin import AdminFlag
from codex.models.comic import Comic
from codex.settings import COMICBOX_CONFIG
from codex.status import Status


class ExtractMetadataImporter(QueryForeignKeysImporter):
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
            import_metadata = AdminFlag.objects.get(key=key).on
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
        all_paths = self.task.files_modified | self.task.files_created
        total_paths = len(all_paths)
        if not total_paths:
            return count

        self.log.info(
            f"Reading tags from {total_paths} comics in {self.library.path}..."
        )
        status = Status(ImportStatusTypes.READ_TAGS, 0, total_paths)
        self.status_controller.start(status, notify=False)

        # Set import_metadata flag
        import_metadata = self._set_import_metadata_flag()

        self.metadata[SKIPPED] = set()
        self.metadata[EXTRACTED] = {}
        for path in all_paths:
            if md := self._extract_path(path, import_metadata=import_metadata):
                self.metadata[EXTRACTED][path] = md
            else:
                self.metadata[SKIPPED].add(path)

        num_skip_paths = len(self.metadata[SKIPPED])
        count = total_paths - num_skip_paths
        self.log.success(f"Read metadata from {count} comics.")
        if num_skip_paths:
            self.log.info(
                f"Skipped {num_skip_paths} comics because metadata appears unchanged."
            )
        self.status_controller.finish(status)
        return count
