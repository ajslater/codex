"""Write tags to comic archives and re-import metadata."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from comicbox.config import get_config
from comicbox.events import BatchFinished, BatchStarted, FileParsed
from comicbox.write import BulkWriteItem, Mode, bulk_write

from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.status import TagWriteStatus
from codex.librarian.worker import WorkerStatusAbortableBase
from codex.models.comic import Comic

if TYPE_CHECKING:
    from comicbox.events import Event

    from codex.librarian.scribe.tasks import BulkTagWriteTask


class TagWriter(WorkerStatusAbortableBase):
    """Write tags via comicbox.bulk_write and trigger re-import."""

    def _on_event(self, event: Event) -> None:
        """Translate comicbox write events into librarian status updates."""
        status = TagWriteStatus()
        match event:
            case BatchStarted():
                status.total = event.total
                status.complete = 0
                self.status_controller.start(status)
            case FileParsed():
                status.complete = event.index
                status.total = event.total
                self.status_controller.update(status)
            case BatchFinished():
                self.status_controller.finish(status)

    def _build_items(
        self, task: BulkTagWriteTask, comic_paths: dict[int, Path]
    ) -> list[BulkWriteItem]:
        """Build BulkWriteItem list from task data."""
        formats = frozenset(task.formats) if task.formats else None
        mode: Mode = task.mode  # pyright: ignore[reportAssignmentType]
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

    def _reimport(self, comic_paths: dict[int, Path]) -> None:
        """Re-import written comics by dispatching ImportTasks grouped by library."""
        if not comic_paths:
            return
        comics = Comic.objects.filter(pk__in=comic_paths.keys()).only(
            "pk", "path", "library_id"
        )
        library_path_map: defaultdict[int, set[str]] = defaultdict(set)
        for comic in comics:
            library_path_map[comic.library_id].add(comic.path)  # pyright: ignore[reportAttributeAccessIssue]

        for library_id, paths in library_path_map.items():
            import_task = ImportTask(
                library_id=library_id,
                files_modified=frozenset(paths),
                force_import_metadata=True,
                check_metadata_mtime=False,
            )
            self.librarian_queue.put(import_task)

    def write_tags(self, task: BulkTagWriteTask) -> None:
        """Execute bulk tag write and re-import."""
        if not task.comic_pks:
            self.log.debug("Tag write called with no comic pks.")
            return

        comics = Comic.objects.filter(pk__in=task.comic_pks).only("pk", "path")
        comic_paths: dict[int, Path] = {comic.pk: Path(comic.path) for comic in comics}

        items = self._build_items(task, comic_paths)
        if not items:
            self.log.debug("Tag write: no patches to apply.")
            return

        written_pks: set[int] = set()
        path_to_pk = {path: pk for pk, path in comic_paths.items()}

        base_config = None
        if task.delete_original:
            cfg = get_config()
            base_config = replace(cfg, general=replace(cfg.general, delete_orig=True))

        for result in bulk_write(
            items,
            on_event=self._on_event,
            cancel=self.abort_event,
            base_config=base_config,
        ):
            if result.written and not result.error:
                pk = path_to_pk.get(result.path)
                if pk is not None:
                    written_pks.add(pk)
            elif result.error:
                self.log.warning(f"Tag write error for {result.path}: {result.error}")

        written_paths = {pk: comic_paths[pk] for pk in written_pks}
        self._reimport(written_paths)
        self.log.info(f"Tag write complete: {len(written_pks)} comics written.")
