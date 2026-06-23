"""Write tags to comic archives and re-import metadata."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, cast

from comicbox.config import get_config
from comicbox.events import (
    BatchFinished,
    BatchStarted,
    FileError,
    FileParsed,
    FileShortCircuited,
)
from comicbox.write import BulkWriteItem, bulk_write

from codex.librarian.notifier.tasks import TAG_WRITE_ERRORS_CHANGED_TASK
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.status import TagWriteStatus
from codex.librarian.scribe.tagwrite_errors import add_tag_write_error
from codex.librarian.worker import WorkerStatusAbortableBase
from codex.models.comic import Comic

if TYPE_CHECKING:
    from comicbox.events import Event
    from comicbox.write import Mode

    from codex.librarian.scribe.tasks import BulkTagWriteTask


class TagWriter(WorkerStatusAbortableBase):
    """Write tags via comicbox.bulk_write and trigger re-import."""

    # One status instance for the whole batch, created on BatchStarted.
    # comicbox runs writes on a thread pool and emits per-file events in
    # *completion* order, each carrying the file's *submission* index.
    # Tracking our own monotonic completion count (rather than echoing
    # ``event.index``) stops the progress bar oscillating. Reusing one
    # instance also keeps ``since_updated`` alive so StatusController's
    # rate-limit throttles instead of firing a DB write per file.
    _status: TagWriteStatus | None = None

    def _on_event(self, event: Event) -> None:
        """Translate comicbox write events into librarian status updates."""
        match event:
            case BatchStarted():
                self._status = TagWriteStatus(complete=0, total=event.total)
                self.status_controller.start(self._status)
            case FileParsed() | FileError() | FileShortCircuited():
                # Every terminal per-file outcome advances progress so the
                # count climbs monotonically to ``total`` even when some
                # files error out.
                if self._status is None:
                    return
                self._status.increment_complete()
                self.status_controller.update(self._status)
            case BatchFinished():
                self.status_controller.finish(self._status)
                self._status = None
            case _:
                pass

    def _build_items(
        self, task: BulkTagWriteTask, comic_paths: dict[int, Path]
    ) -> list[BulkWriteItem]:
        """Build BulkWriteItem list from task data."""
        formats = frozenset(task.formats) if task.formats else None
        mode = cast("Mode", task.mode)
        items = []
        for pk, path in comic_paths.items():
            if task.per_comic_patches and pk in task.per_comic_patches:
                patch = task.per_comic_patches[pk]
            elif task.patch:
                patch = task.patch
            else:
                continue
            items.append(
                BulkWriteItem(
                    path=path,
                    patch=patch,
                    mode=mode,
                    formats=formats,
                )
            )
        return items

    def _reimport_unwatched(self, comic_paths: dict[int, Path]) -> None:
        """Re-import comics in libraries without filesystem event watching."""
        if not comic_paths:
            return
        comics = Comic.objects.filter(pk__in=comic_paths.keys()).only(
            "pk", "path", "library_id", "library__events"
        )
        library_path_map: defaultdict[int, set[str]] = defaultdict(set)
        for comic in comics:
            if not comic.library.events:
                library_path_map[comic.library_id].add(comic.path)  # pyright: ignore[reportAttributeAccessIssue]

        for library_id, paths in library_path_map.items():
            import_task = ImportTask(
                library_id=library_id,
                files_modified=frozenset(paths),
                force_import_metadata=True,
                check_metadata_mtime=False,
            )
            self.librarian_queue.put(import_task)

    @staticmethod
    def _build_base_config(task: BulkTagWriteTask):
        """Return a config with delete_orig set, or None when not deleting."""
        if not task.delete_original:
            return None
        cfg = get_config()
        return replace(cfg, general=replace(cfg.general, delete_orig=True))

    def _collect_written_pks(
        self,
        items: list[BulkWriteItem],
        path_to_pk: dict[Path, int],
        base_config,
    ) -> set[int]:
        """Run bulk_write and return pks that were successfully written."""
        written_pks: set[int] = set()
        had_errors = False
        for result in bulk_write(
            items,
            on_event=self._on_event,
            cancel=self.abort_event,
            base_config=base_config,
        ):
            if result.error:
                self.log.warning(f"Tag write error for {result.path}: {result.error}")
                add_tag_write_error(str(result.path), str(result.error))
                had_errors = True
                continue
            if not result.written:
                continue
            pk = path_to_pk.get(result.path)
            if pk is not None:
                written_pks.add(pk)
        if had_errors:
            # Surface the failures to admins (red badge + Tagging-tab panel).
            self.librarian_queue.put(TAG_WRITE_ERRORS_CHANGED_TASK)
        return written_pks

    def write_tags(self, task: BulkTagWriteTask) -> None:
        """Execute bulk tag write and re-import."""
        if not task.comic_pks:
            self.log.debug("Tag write called with no comic pks.")
            return

        # Never write archives in read-only libraries, even if a task somehow
        # carries their pks (the API funnel already drops them; this is a backstop).
        comics = (
            Comic.objects.filter(pk__in=task.comic_pks)
            .exclude(library__read_only=True)
            .only("pk", "path")
        )
        comic_paths: dict[int, Path] = {comic.pk: Path(comic.path) for comic in comics}

        items = self._build_items(task, comic_paths)
        if not items:
            self.log.debug("Tag write: no patches to apply.")
            return

        path_to_pk = {path: pk for pk, path in comic_paths.items()}
        base_config = self._build_base_config(task)
        written_pks = self._collect_written_pks(items, path_to_pk, base_config)

        written_paths = {pk: comic_paths[pk] for pk in written_pks}
        self._reimport_unwatched(written_paths)
        self.log.info(f"Tag write complete: {len(written_pks)} comics written.")
