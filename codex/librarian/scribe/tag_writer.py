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
from codex.librarian.scribe.tagwrite_moves import register_tag_write_move
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
        delete_keys = frozenset(task.delete_keys) if task.delete_keys else None
        items = []
        for pk, path in comic_paths.items():
            if task.per_comic_patches and pk in task.per_comic_patches:
                patch = task.per_comic_patches[pk]
            else:
                patch = task.patch or {}
            if not patch and not delete_keys:
                continue
            items.append(
                BulkWriteItem(
                    path=path,
                    patch=patch,
                    mode=mode,
                    formats=formats,
                    delete_keys=delete_keys,
                )
            )
        return items

    @staticmethod
    def _build_base_config(task: BulkTagWriteTask):
        """
        Return a config with delete_orig set, or None when not deleting.

        Never pass codex's read-side ``COMICBOX_CONFIG`` here. Comicbox
        unions a write's ``delete_keys`` with the base config's, and that
        config carries the big parse-skip set of schema fields codex
        doesn't consume (pages, cover_image, prices, ...). Using it as a
        write base would strip every one of those from the user's archive.
        """
        if not task.delete_original:
            return None
        cfg = get_config()
        return replace(cfg, general=replace(cfg.general, delete_orig=True))

    def _collect_written_paths(
        self,
        items: list[BulkWriteItem],
        path_to_pk: dict[Path, int],
        base_config,
    ) -> dict[int, Path]:
        """
        Run bulk_write; map successfully written pks to their on-disk paths.

        The mapped path is the *final* one comicbox reports: writing an
        unwritable archive (CBR/CBT/CB7) repacks it as a CBZ at a new path,
        and every later step — rename, DB sync — must chase the file there,
        not the submitted path the DB still holds.
        """
        written_paths: dict[int, Path] = {}
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
                written_paths[pk] = result.final_path or result.path
        if had_errors:
            # Surface the failures to admins (red badge + Tagging-tab panel).
            self.librarian_queue.put(TAG_WRITE_ERRORS_CHANGED_TASK)
        return written_paths

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
        """Execute bulk tag write, optional rename, and DB sync."""
        if not task.comic_pks:
            self.log.debug("Tag write called with no comic pks.")
            return

        comic_paths, lib_of, library_events = self._resolve_comics(task)
        items = self._build_items(task, comic_paths)
        if not items and not task.rename:
            self.log.debug("Tag write: no patches to apply.")
            return

        written_paths: dict[int, Path] = {}
        if items:
            path_to_pk = {path: pk for pk, path in comic_paths.items()}
            base_config = self._build_base_config(task)
            written_paths = self._collect_written_paths(items, path_to_pk, base_config)

        renamed_paths: dict[int, Path] = {}
        if task.rename:
            # Rename-only (no patch) renames every resolved comic from its
            # existing on-archive metadata; with a patch, only the written
            # ones. Renames chase the written file to its post-conversion
            # path, not the possibly-stale DB path.
            candidates = set(written_paths) if items else set(comic_paths)
            current_paths = {**comic_paths, **written_paths}
            renamed_paths = self._rename_comics(candidates, current_paths)

        self._sync_db(
            task, comic_paths, written_paths, renamed_paths, lib_of, library_events
        )
        num_written = len(written_paths)
        num_renamed = len(renamed_paths)
        self.log.info(
            f"Tag write complete: {num_written} written, {num_renamed} renamed."
        )

    def _rename_one(self, old_path: Path) -> Path | None:
        """
        Rename one archive to the comicbox (comicfn2dict) filename scheme.

        Returns the new path, or None when the name is unchanged or no name
        could be built. Raises ``FileExistsError`` on a collision with a
        *different* file so the caller reports it without clobbering anything.

        Codex performs the rename itself rather than calling comicbox's
        ``rename_file``, which derives its own destination and does a bare
        ``Path.rename`` — there is no way to hand it a corrected target, and
        the extension it renders is not the archive's own (see below).
        """
        with Comicbox(old_path, config=COMICBOX_CONFIG) as car:
            target = car.to_string(MetadataFormats.FILENAME)
        # A rendered name always ends in an extension, but not necessarily
        # this file's: ``ext`` is a *metadata* field, and codex's read config
        # deletes it, so comicfn2dict falls back to its "cbz" default and
        # every PDF/CBR/CBT/CB7 would be renamed to a ".cbz" name it isn't.
        # The archive on disk is the authority, so keep its real suffix.
        # A name that is nothing but an extension (no metadata parsed at all)
        # would make a hidden file, so treat it as no name at all.
        if not target or target.startswith("."):
            self.log.warning(f"Rename skipped; no filename built for {old_path}")
            return None
        new_path = (old_path.parent / target).with_suffix(old_path.suffix)
        if new_path == old_path:
            return None
        if new_path.exists() and not new_path.samefile(old_path):
            reason = f"rename target already exists: {new_path}"
            raise FileExistsError(reason)
        old_path.rename(new_path)
        return new_path

    def _rename_comics(
        self,
        candidates: set[int],
        current_paths: dict[int, Path],
    ) -> dict[int, Path]:
        """Rename candidate comics on disk. Return new paths by pk."""
        renamed_paths: dict[int, Path] = {}
        had_errors = False
        for pk in candidates:
            old_path = current_paths[pk]
            try:
                new_path = self._rename_one(old_path)
            except Exception as exc:
                self.log.warning(f"Rename error for {old_path}: {exc}")
                add_tag_write_error(str(old_path), f"rename failed: {exc}")
                had_errors = True
                continue
            if new_path is None or new_path == old_path:
                continue
            renamed_paths[pk] = new_path
        if had_errors:
            self.librarian_queue.put(TAG_WRITE_ERRORS_CHANGED_TASK)
        return renamed_paths

    @staticmethod
    def _sync_ops_for_comic(
        db_path: Path,
        written_path: Path | None,
        renamed_path: Path | None,
        *,
        watched: bool,
        delete_original: bool,
    ) -> tuple[str | None, str | None, str | None]:
        """
        Classify one comic's on-disk outcome into DB sync operations.

        Returns (moved_dest, modified_path, created_path); each is None when
        that operation isn't needed. See ``_sync_db`` for the rationale
        behind each case.
        """
        if written_path is None and renamed_path is None:
            return None, None, None
        converted = written_path is not None and written_path != db_path
        end_path = str(renamed_path or written_path or db_path)
        if converted and not delete_original:
            # The DB comic is the untouched original; the CBZ is a new file.
            return None, None, None if watched else end_path
        if converted:
            # New inode: nothing downstream can pair this move; record it
            # for watched libraries too.
            return end_path, end_path, None
        if renamed_path is not None:
            # Codex performed this rename, so it states the move rather
            # than leaving the watcher to re-infer it; watched too.
            modify = end_path if written_path is not None else None
            return end_path, modify, None
        if watched:
            return None, None, None
        return None, end_path, None

    @staticmethod
    def _guard_move_paths(src: str, written_path: Path | None, move_to: str) -> None:
        """
        Hold every path this move passes through until the importer applies it.

        A scan that lands mid-batch reports the same conversion as an
        unrelated delete plus create and, being enqueued first, reaches
        the importer first. Registering the DB's now-dead source, the
        interim archive the write produced, and the final destination
        makes that scan a no-op for them, so the move below still finds
        its source row — and its bookmarks — in place. See
        ``codex.librarian.scribe.tagwrite_moves``.
        """
        waypoints = (str(written_path),) if written_path else ()
        register_tag_write_move(src, move_to, waypoints)

    def _sync_db(
        self,
        task: BulkTagWriteTask,
        comic_paths: dict[int, Path],
        written_paths: dict[int, Path],
        renamed_paths: dict[int, Path],
        lib_of: dict[int, int],
        library_events: dict[int, bool],
    ) -> None:
        """
        Sync the DB to the on-disk outcome of the write + rename, watcher-aware.

        Three on-disk outcomes need a DB move or re-read:

        Conversion (CBR/CBT/CB7 repacked as CBZ during the write, original
        deleted): the new archive is a *new inode*, which neither the watcher
        nor the poller can pair into a move — left alone, the row would be
        deleted and recreated, losing bookmarks. Codex must record the move
        itself, for watched libraries too; the watcher's later add/delete
        events reconcile as no-ops against the already-moved row. A batch
        long enough to force a mid-batch watcher flush (or a poll that lands
        during it) would otherwise get that scan's delete in first, so every
        path a move passes through is registered in ``tagwrite_moves`` and
        the importer holds it for this task. When the
        original is kept (``delete_original`` off), the DB comic is untouched
        and the converted CBZ is simply a new file: watched libraries see its
        create event, unwatched ones are told here.

        Pure rename (same path reported back): codex records the move
        itself, for watched libraries too. A watcher can only recognize a
        rename by pairing its delete and add on a matching inode, and that
        pairing is not dependable. An in-place PDF tag write saves to a
        temp file and ``replace()``s it over the original, so the file
        carries a *new* inode that the row's stored one can never match;
        even a same-inode archive goes unpaired when the delete and add
        land in different watcher batches. An unpaired rename deletes the
        row and recreates it, losing bookmarks and read state. Duplicating
        a move the watcher does pair costs nothing: whichever copy lands
        second is dropped by ``_remove_file_move_collisions`` for an
        occupied destination, or matches no source row in
        ``_bulk_comics_move_prepare``. The move is targeted, so
        ``move_and_modify_dirs`` runs before the per-comic ``read`` phase,
        and its paths are held against a mid-batch scan exactly as a
        conversion's are.

        In-place write (no conversion, no rename): watched libraries re-read
        via the watcher's modify event; unwatched ones are told here.
        """
        moved: defaultdict[int, dict[str, str]] = defaultdict(dict)
        modified: defaultdict[int, set[str]] = defaultdict(set)
        created: defaultdict[int, set[str]] = defaultdict(set)
        for pk, db_path in comic_paths.items():
            library_id = lib_of[pk]
            move_to, modify, create = self._sync_ops_for_comic(
                db_path,
                written_paths.get(pk),
                renamed_paths.get(pk),
                watched=library_events.get(library_id, False),
                delete_original=task.delete_original,
            )
            if move_to:
                src = str(db_path)
                moved[library_id][src] = move_to
                self._guard_move_paths(src, written_paths.get(pk), move_to)
            if modify:
                modified[library_id].add(modify)
            if create:
                created[library_id].add(create)

        for library_id in moved.keys() | modified.keys() | created.keys():
            import_task = ImportTask(
                library_id=library_id,
                files_moved=moved.get(library_id, {}),
                files_modified=frozenset(modified.get(library_id, ())),
                files_created=frozenset(created.get(library_id, ())),
                force_import_metadata=True,
                check_metadata_mtime=False,
            )
            self.librarian_queue.put(import_task)
