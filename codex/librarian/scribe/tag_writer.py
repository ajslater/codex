"""Write tags to comic archives and re-import metadata."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, cast

from comicbox.box import Comicbox
from comicbox.config import get_config
from comicbox.events import (
    BatchFinished,
    BatchStarted,
    FileError,
    FileParsed,
    FileShortCircuited,
)
from comicbox.formats import MetadataFormats
from comicbox.write import BulkWriteItem, bulk_write

from codex.librarian.notifier.tasks import TAG_WRITE_ERRORS_CHANGED_TASK
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.status import TagWriteStatus
from codex.librarian.scribe.tagwrite_errors import add_tag_write_error
from codex.librarian.worker import WorkerStatusAbortableBase
from codex.models.comic import Comic
from codex.settings import COMICBOX_CONFIG

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

    @staticmethod
    def _resolve_comics(
        task: BulkTagWriteTask,
    ) -> tuple[dict[int, Path], dict[int, int], dict[int, bool]]:
        """
        Resolve writable comics to path / library maps.

        Never returns comics in read-only libraries, even if a task somehow
        carries their pks (the API funnel already drops them; this is a
        backstop). Returns (path-by-pk, library-id-by-pk, watcher-by-library).
        """
        comics = (
            Comic.objects.filter(pk__in=task.comic_pks)
            .exclude(library__read_only=True)
            .select_related("library")
            .only("pk", "path", "library__events")
        )
        comic_paths: dict[int, Path] = {}
        lib_of: dict[int, int] = {}
        library_events: dict[int, bool] = {}
        for comic in comics:
            comic_paths[comic.pk] = Path(comic.path)
            lib_of[comic.pk] = comic.library_id  # pyright: ignore[reportAttributeAccessIssue]
            library_events[comic.library_id] = comic.library.events  # pyright: ignore[reportAttributeAccessIssue]
        return comic_paths, lib_of, library_events

    def write_tags(self, task: BulkTagWriteTask) -> None:
        """Execute bulk tag write, optional rename, and re-import."""
        if not task.comic_pks:
            self.log.debug("Tag write called with no comic pks.")
            return

        comic_paths, lib_of, library_events = self._resolve_comics(task)
        items = self._build_items(task, comic_paths)
        if not items and not task.rename:
            self.log.debug("Tag write: no patches to apply.")
            return

        written_pks: set[int] = set()
        if items:
            path_to_pk = {path: pk for pk, path in comic_paths.items()}
            base_config = self._build_base_config(task)
            written_pks = self._collect_written_pks(items, path_to_pk, base_config)

        renamed_pks: set[int] = set()
        if task.rename:
            # Rename-only (no patch) renames every resolved comic from its
            # existing on-archive metadata; with a patch, only the written ones.
            candidates = written_pks if items else set(comic_paths)
            renamed_pks = self._rename_comics(
                candidates,
                comic_paths,
                lib_of,
                library_events,
                tags_written=bool(items),
            )

        # Non-renamed written comics keep the existing unwatched re-import path;
        # renamed comics are synced inside _rename_comics (their old path is gone).
        non_renamed = {
            pk: comic_paths[pk] for pk in written_pks if pk not in renamed_pks
        }
        self._reimport_unwatched(non_renamed)
        self.log.info(
            f"Tag write complete: {len(written_pks)} written, {len(renamed_pks)} renamed."
        )

    def _rename_one(self, old_path: Path) -> Path | None:
        """
        Rename one archive to the comicbox (comicfn2dict) filename scheme.

        Returns the new path, or None when the name is unchanged or no name
        could be built. Raises ``FileExistsError`` on a collision with a
        *different* file so the caller reports it without clobbering anything
        (comicbox's ``rename_file`` does a bare ``Path.rename``).
        """
        with Comicbox(old_path, config=COMICBOX_CONFIG) as car:
            # to_string(FILENAME) is exactly what rename_file() derives the
            # name from (schema.dumps(_to_dict(FILENAME))), so this pre-check
            # targets the precise destination rename_file() will use.
            target = car.to_string(MetadataFormats.FILENAME)
            if not target:
                self.log.warning(f"Rename skipped; no filename built for {old_path}")
                return None
            new_path = old_path.parent / target
            if new_path == old_path:
                return None
            if new_path.exists() and not new_path.samefile(old_path):
                reason = f"rename target already exists: {new_path}"
                raise FileExistsError(reason)
            car.rename_file()
            renamed = car.get_path()
        return renamed or new_path

    def _rename_comics(
        self,
        candidates: set[int],
        comic_paths: dict[int, Path],
        lib_of: dict[int, int],
        library_events: dict[int, bool],
        *,
        tags_written: bool,
    ) -> set[int]:
        """Rename candidate comics and sync the DB. Return the renamed pks."""
        # library_id -> {old_path_str: new_path_str}
        moved: defaultdict[int, dict[str, str]] = defaultdict(dict)
        renamed_pks: set[int] = set()
        had_errors = False
        for pk in candidates:
            old_path = comic_paths[pk]
            try:
                new_path = self._rename_one(old_path)
            except Exception as exc:
                self.log.warning(f"Rename error for {old_path}: {exc}")
                add_tag_write_error(str(old_path), f"rename failed: {exc}")
                had_errors = True
                continue
            if new_path is None or new_path == old_path:
                continue
            moved[lib_of[pk]][str(old_path)] = str(new_path)
            renamed_pks.add(pk)
        if had_errors:
            self.librarian_queue.put(TAG_WRITE_ERRORS_CHANGED_TASK)
        self._enqueue_rename_imports(moved, library_events, tags_written=tags_written)
        return renamed_pks

    def _enqueue_rename_imports(
        self,
        moved: dict[int, dict[str, str]],
        library_events: dict[int, bool],
        *,
        tags_written: bool,
    ) -> None:
        """
        Sync the DB for renamed comics, watcher-aware.

        Watched libraries: enqueue nothing — the watcher's inode move-detection
        emits the ``files_moved`` import and the tag-write content-modify
        refreshes metadata, so a self-enqueued move would only duplicate it.
        Unwatched libraries: enqueue one targeted move import that updates the
        path and, when tags were written, re-reads the new file's metadata
        (``move_and_modify_dirs`` runs before the per-comic ``read`` phase).
        """
        for library_id, lib_moved in moved.items():
            if library_events.get(library_id):
                continue
            files_modified = (
                frozenset(lib_moved.values()) if tags_written else frozenset()
            )
            import_task = ImportTask(
                library_id=library_id,
                files_moved=dict(lib_moved),
                files_modified=files_modified,
                force_import_metadata=True,
                check_metadata_mtime=False,
            )
            self.librarian_queue.put(import_task)
