"""Extract metadata from comic archive."""

from collections.abc import MutableMapping
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

from comicbox.process import iter_process_files
from comicbox.schemas.comicbox import PAGE_COUNT_KEY

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

    def _get_import_metadata_flag(self) -> bool:
        """Set import_metadata flag."""
        if self.task.force_import_metadata:
            import_metadata = True
        else:
            key = AdminFlagChoices.IMPORT_METADATA.value
            import_metadata = AdminFlag.objects.only("on").get(key=key).on
        if not import_metadata:
            self.log.warning("Admin flag set to NOT import metadata.")
        return import_metadata

    def _get_old_comic_mtime(
        self, old_comic: MutableMapping[str, datetime | str | int]
    ) -> datetime | None:
        if not self.task.check_metadata_mtime:
            return None
        old_mtime: datetime = old_comic.pop("metadata_mtime")  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
        if old_mtime and (
            old_mtime.tzinfo is None or old_mtime.tzinfo.utcoffset(old_mtime) is None
        ):
            old_mtime = old_mtime.replace(tzinfo=UTC)
        return old_mtime

    def _get_all_old_comic_values(
        self,
        all_paths: frozenset[str],
    ) -> tuple[
        MappingProxyType[str, datetime], MappingProxyType[str, dict[str, str | int]]
    ]:
        """Get some old comic values."""
        values = ["path", "page_count", "file_type"]
        if self.task.check_metadata_mtime:
            values.append("metadata_mtime")
        old_comics = Comic.objects.filter(path__in=all_paths).values(*values)
        old_comic_values = {}
        old_comic_mtimes = {}
        for old_comic in old_comics:
            old_path_str = old_comic.pop("path")
            if old_mtime := self._get_old_comic_mtime(old_comic):
                old_comic_mtimes[old_path_str] = old_mtime
            old_comic_values[old_path_str] = old_comic
        return MappingProxyType(old_comic_mtimes), MappingProxyType(old_comic_values)

    def _extract_post_process_comic(
        self,
        path: Path,
        value: tuple[MutableMapping, BaseException | None],
        all_old_comic_values: MappingProxyType[str, dict[str, str | int]],
        status: ImporterReadComicsStatus,
    ):
        if self.abort_event.is_set():
            return True
        md, exc = value
        path_str = str(path)
        if exc:
            failed_import = {path: exc}
            self.metadata[FIS].update(failed_import)
        if md:
            old_comic = all_old_comic_values.get(path_str, {})
            old_file_type = old_comic.get("file_type")
            old_page_count = old_comic.get(PAGE_COUNT_KEY)

            # Remove similar info to avoid update if nothing changed.
            if old_page_count == md.get("page_count"):
                md.pop("page_count", None)
            if old_file_type == md.get("file_type"):
                md.pop("file_type", None)

            if md:
                md["path"] = path_str

            self.metadata[EXTRACTED][path_str] = md
        else:
            self.metadata[SKIPPED].add(path_str)
        status.increment_complete()
        self.status_controller.update(status)
        return False

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
        if not status:
            status = ImporterReadComicsStatus(0, total_paths)
        else:
            status.complete = 0
            status.total = total_paths
            self.status_controller.update(status)

        try:
            if not total_paths:
                return count

            self.log.debug(
                f"Reading tags from {total_paths} comics in {self.library.path}..."
            )
            self.status_controller.start(status, notify=True)

            # Set import_metadata flag
            import_metadata = self._get_import_metadata_flag()
            all_old_comic_mtimes, all_old_comic_values = self._get_all_old_comic_values(
                all_paths
            )

            for path, value in iter_process_files(
                all_paths,
                config=COMICBOX_CONFIG,
                logger=self.log,
                old_mtime_map=all_old_comic_mtimes,
                full_metadata=import_metadata,
            ):
                if self._extract_post_process_comic(
                    path, value, all_old_comic_values, status
                ):
                    break

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
