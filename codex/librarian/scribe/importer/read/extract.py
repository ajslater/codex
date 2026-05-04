"""Extract metadata from comic archive."""

from collections.abc import Iterable, MutableMapping
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

from comicbox.process import ReadResult, iter_process_files
from comicbox.schemas.comicbox import PAGE_COUNT_KEY

from codex.choices.admin import AdminFlagChoices
from codex.librarian.scribe.importer.const import (
    EXTRACTED,
    EXTRACTED_STAT_ONLY,
    FIS,
    SKIPPED,
)
from codex.librarian.scribe.importer.read.aggregate_path import (
    AggregateMetadataImporter,
)
from codex.librarian.scribe.importer.statii.read import ImporterReadComicsStatus
from codex.models.admin import AdminFlag
from codex.models.comic import Comic
from codex.settings import COMICBOX_CONFIG, LOGLEVEL
from codex.startup.loguru import CODEX_LOG_FORMAT


class ExtractMetadataImporter(AggregateMetadataImporter):
    """Aggregate metadata from comics to prepare for importing."""

    @staticmethod
    def _filesystem_mtime_prefilter(
        all_paths: Iterable[str],
        old_mtime_map: MappingProxyType[str, datetime],
    ) -> tuple[frozenset[str], frozenset[str]]:
        """
        Drop paths whose filesystem mtime has not advanced since last import.

        Comicbox's worker performs an embedded-metadata-mtime check too,
        but only after opening the archive — for CBR that's an unrar
        spawn + header parse. Filtering here saves the archive open on
        the common case (re-import where the archive is unchanged on
        disk).

        Filesystem mtime can lag the embedded mtime (e.g. a user resaved
        ``ComicInfo.xml`` without touching the archive's mtime), but
        cannot lead it: any modification that updates the embedded
        mtime also updates the archive's mtime. So this filter produces
        only false positives (let through, then no-op'd by the worker
        check), never false negatives.

        Returns ``(survivors, skipped_paths)`` so the caller can
        account for skips in the SKIPPED set.
        """
        survivors: set[str] = set()
        skipped: set[str] = set()
        for path in all_paths:
            old_mtime = old_mtime_map.get(path)
            if old_mtime is None:
                # No prior record (new comic) — must extract.
                survivors.add(path)
                continue
            try:
                fs_mtime = datetime.fromtimestamp(Path(path).stat().st_mtime, tz=UTC)
            except OSError:
                # Filesystem hiccup or vanished file — let the worker
                # produce a FailedImport with the real error.
                survivors.add(path)
                continue
            if fs_mtime > old_mtime:
                survivors.add(path)
            else:
                skipped.add(path)
        return frozenset(survivors), frozenset(skipped)

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

    @staticmethod
    def _envelope_deltas(
        result: ReadResult, old_comic: dict[str, Any]
    ) -> dict[str, Any]:
        """Build the subset of envelope fields that actually changed vs DB."""
        delta: dict[str, Any] = {}
        if (mtime := result.get("metadata_mtime")) is not None:
            delta["metadata_mtime"] = mtime
        new_page_count = result.get("page_count")
        if (
            new_page_count is not None
            and old_comic.get(PAGE_COUNT_KEY) != new_page_count
        ):
            delta["page_count"] = new_page_count
        new_file_type = result.get("file_type")
        if new_file_type is not None and old_comic.get("file_type") != new_file_type:
            delta["file_type"] = new_file_type
        return delta

    def _extract_post_process_comic(
        self,
        path: Path,
        value: tuple[ReadResult, BaseException | None],
        all_old_comic_values: MappingProxyType[str, dict[str, str | int]],
        status: ImporterReadComicsStatus,
    ):
        if self.abort_event.is_set():
            return True
        result, exc = value
        path_str = str(path)
        if exc:
            self.metadata[FIS].update({path: exc})
            self.metadata[SKIPPED].add(path_str)
            status.increment_complete()
            self.status_controller.update(status)
            return False

        old_comic = all_old_comic_values.get(path_str, {})
        envelope_md = self._envelope_deltas(result, old_comic)
        tags = result.get("tags")

        if tags is None:
            # Comicbox fast-skipped the tag re-extraction (mtime
            # unchanged or full_metadata=False). Route any envelope
            # changes through the stat-only path so aggregate doesn't
            # see an empty-tag md and clobber the comic's existing
            # browser-group FKs with the empty default groups.
            if envelope_md:
                envelope_md["path"] = path_str
                self.metadata[EXTRACTED_STAT_ONLY][path_str] = envelope_md
            self.metadata[SKIPPED].add(path_str)
        else:
            # Real tag extraction. Envelope wins on key conflict.
            md: dict[str, Any] = {**tags, **envelope_md, "path": path_str}
            self.metadata[EXTRACTED][path_str] = md
        status.increment_complete()
        self.status_controller.update(status)
        return False

    def _init_extract_status(
        self,
        status: ImporterReadComicsStatus | None,
        total_paths: int,
    ) -> ImporterReadComicsStatus:
        """Reset/create the read-comics status object for an extract pass."""
        if status is None:
            return ImporterReadComicsStatus(0, total_paths)
        status.complete = 0
        status.total = total_paths
        self.status_controller.update(status)
        return status

    def _apply_filesystem_prefilter(
        self,
        all_paths: frozenset[str],
        all_old_comic_mtimes: MappingProxyType[str, datetime],
        status: ImporterReadComicsStatus,
    ) -> frozenset[str]:
        """
        Skip archive-open cost via filesystem stat mtime pre-filter.

        Worker still rechecks the embedded mtime for paths that pass
        through, so a touch-without-content-change still short-circuits
        inside the worker.
        """
        if not all_old_comic_mtimes:
            return all_paths
        paths_to_extract, prefilter_skipped = self._filesystem_mtime_prefilter(
            all_paths, all_old_comic_mtimes
        )
        if prefilter_skipped:
            self.metadata[SKIPPED].update(prefilter_skipped)
            skipped_n = len(prefilter_skipped)
            self.log.debug(
                f"Skipped archive open for {skipped_n} comics via filesystem mtime pre-filter."
            )
            status.increment_complete(skipped_n)
            self.status_controller.update(status)
        return paths_to_extract

    def _run_extract_loop(
        self,
        paths_to_extract: frozenset[str],
        all_old_comic_mtimes: MappingProxyType[str, datetime],
        all_old_comic_values: MappingProxyType[str, dict[str, str | int]],
        status: ImporterReadComicsStatus,
        *,
        import_metadata: bool,
    ) -> None:
        """Stream the comicbox extraction results into the metadata dict."""
        for path, value in iter_process_files(
            paths_to_extract,
            config=COMICBOX_CONFIG,
            logger=self.log,
            worker_log_config={
                "level": LOGLEVEL,
                "format": CODEX_LOG_FORMAT,
                "sink": "stdout",  # comicbox only accepts one sink
            },
            old_mtime_map=all_old_comic_mtimes,
            full_metadata=import_metadata,
        ):
            if self._extract_post_process_comic(
                path, value, all_old_comic_values, status
            ):
                break

    def extract_metadata(self, status=None) -> int:
        """Extract comic metadata into memory."""
        count = 0
        # SKIPPED is per-extract; EXTRACTED is per-extract (drained by
        # aggregate). EXTRACTED_STAT_ONLY is per-extract (drained by
        # aggregate). FIS accumulates across chunks and is consumed
        # later by the fail_imports phase, so use ``setdefault`` so
        # a second pass over a different chunk doesn't drop the first
        # chunk's failed imports.
        self.metadata[SKIPPED] = set()
        self.metadata[EXTRACTED] = {}
        self.metadata[EXTRACTED_STAT_ONLY] = {}
        self.metadata.setdefault(FIS, {})
        all_paths = self.task.files_modified | self.task.files_created
        self.task.files_modified = frozenset()
        self.task.files_created = frozenset()
        total_paths = len(all_paths)
        status = self._init_extract_status(status, total_paths)

        try:
            if not total_paths:
                return count

            self.log.debug(
                f"Reading tags from {total_paths} comics in {self.library.path}..."
            )
            self.status_controller.start(status, notify=True)

            import_metadata = self._get_import_metadata_flag()
            all_old_comic_mtimes, all_old_comic_values = self._get_all_old_comic_values(
                all_paths
            )
            paths_to_extract = self._apply_filesystem_prefilter(
                all_paths, all_old_comic_mtimes, status
            )
            self._run_extract_loop(
                paths_to_extract,
                all_old_comic_mtimes,
                all_old_comic_values,
                status,
                import_metadata=import_metadata,
            )

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
