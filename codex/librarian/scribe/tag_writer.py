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
from django.core.cache import cache
from django.utils.timezone import now

from codex.librarian.notifier.tasks import (
    LIBRARY_CHANGED_TASK,
    TAG_WRITE_ERRORS_CHANGED_TASK,
)
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.status import TagWriteStatus
from codex.librarian.scribe.tagwrite_errors import add_tag_write_error
from codex.librarian.scribe.tagwrite_rename import (
    RenamePlan,
    build_predict_config,
    plan_rename,
    predict_name,
    will_convert,
)
from codex.librarian.scribe.timestamp_update import TimestampUpdater
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
    ) -> tuple[dict[int, Path], dict[int, int]]:
        """
        Resolve writable comics to path / library maps.

        Never returns comics in read-only libraries, even if a task somehow
        carries their pks (the API funnel already drops them; this is a
        backstop). Returns (path-by-pk, library-id-by-pk).

        Whether a library is watched no longer changes anything here: every
        move is applied inline, and the re-read is requested either way
        because a watched library's own re-read is stat-only unless the
        import-metadata flag is on.
        """
        comics = (
            Comic.objects.filter(pk__in=task.comic_pks)
            .exclude(library__read_only=True)
            .only("pk", "path", "library")
        )
        comic_paths: dict[int, Path] = {}
        lib_of: dict[int, int] = {}
        for comic in comics:
            comic_paths[comic.pk] = Path(comic.path)
            lib_of[comic.pk] = comic.library_id  # pyright: ignore[reportAttributeAccessIssue]
        return comic_paths, lib_of

    def write_tags(self, task: BulkTagWriteTask) -> None:
        """
        Rename each archive to its final name, then write tags there.

        Renaming first, and applying each move to the database before this
        method returns, is what keeps a comic's bookmarks through the churn.
        Every path a write moves through used to be reconciled *later*, by
        an ``ImportTask`` queued behind whatever else the scribe was doing —
        so a scan landing in between saw an unexplained delete plus create,
        deleted the row by its now-dead path, and cascaded the bookmarks
        away. Doing the move here, on the scribe's own thread, means no scan
        can be processed while the database disagrees with the disk: a
        stale delete finds no row and a stale create converges onto the row
        already sitting at that path.

        A conversion (CBR/CBT/CB7 repacked as a CBZ) still moves the file
        after the write, so it is synced the same way as soon as the batch
        finishes. Only the metadata re-read is left to a queued task, which
        is safe because it names a path the database already holds.
        """
        if not task.comic_pks:
            self.log.debug("Tag write called with no comic pks.")
            return

        comic_paths, lib_of = self._resolve_comics(task)
        if not self._build_items(task, comic_paths) and not task.rename:
            self.log.debug("Tag write: no patches to apply.")
            return

        renamed_paths = self._rename_first(task, comic_paths, lib_of)
        current_paths = {**comic_paths, **renamed_paths}

        written_paths = self._write(task, current_paths)
        converted_paths = self._sync_conversions(
            task, current_paths, written_paths, lib_of
        )
        # A kept original leaves the row where it is and the new CBZ is
        # simply a new file, so its scheme name is applied after the write.
        post_renamed = self._rename_kept_conversions(
            task, current_paths, written_paths, converted_paths
        )

        self._enqueue_rereads(
            current_paths, written_paths, converted_paths, post_renamed, lib_of
        )
        num_renamed = len(renamed_paths) + len(post_renamed)
        reason = (
            f"Tag write complete: {len(written_paths)} written, {num_renamed} renamed."
        )
        self.log.info(reason)

    def _write(
        self, task: BulkTagWriteTask, current_paths: dict[int, Path]
    ) -> dict[int, Path]:
        """Write tags at each comic's post-rename path."""
        items = self._build_items(task, current_paths)
        if not items:
            return {}
        path_to_pk = {path: pk for pk, path in current_paths.items()}
        base_config = self._build_base_config(task)
        return self._collect_written_paths(items, path_to_pk, base_config)

    def _plan_renames(
        self, task: BulkTagWriteTask, comic_paths: dict[int, Path]
    ) -> list[RenamePlan]:
        """
        Build every comic's rename plan, dropping the ones that can't run.

        A plan is dropped when two comics in the batch predict the same
        name, when either the rename target or the destination a later
        conversion needs is already taken on disk or in the database, or
        when no name could be built at all. Both ends matter: comicbox
        refuses to convert onto an existing file, and that refusal would
        land *after* the rename and its database move had already happened.
        """
        config = build_predict_config(task.delete_keys, task.mode)
        plans: list[RenamePlan] = []
        claimed: dict[Path, int] = {}
        for pk, old_path in comic_paths.items():
            if not task.delete_original and will_convert(old_path):
                # Renamed after the write instead; the row stays put.
                continue
            try:
                plan = plan_rename(pk, old_path, self._patch_for(task, pk), config)
            except Exception as exc:
                self._report_error(old_path, f"rename failed: {exc}")
                continue
            if plan is None:
                self.log.warning(f"Rename skipped; no filename built for {old_path}")
                continue
            if plan.target == old_path and plan.final_path == old_path:
                continue
            if reason := self._claim_conflict(plan, claimed, comic_paths):
                self._report_error(old_path, reason)
                continue
            claimed[plan.target] = pk
            claimed[plan.final_path] = pk
            plans.append(plan)
        return plans

    @staticmethod
    def _patch_for(task: BulkTagWriteTask, pk: int) -> dict | None:
        """Return the patch this comic will be written with, if any."""
        if task.per_comic_patches and pk in task.per_comic_patches:
            return task.per_comic_patches[pk]
        return task.patch or None

    @staticmethod
    def _destination_conflict(
        plan: RenamePlan, destination: Path, claimed: dict[Path, int]
    ) -> str:
        """Return why one destination is unavailable, or ""."""
        other = claimed.get(destination)
        if other is not None and other != plan.pk:
            return f"another comic in this batch renames to {destination}"
        if destination == plan.old_path:
            return ""
        if destination.exists() and not (
            # A case-only rename on a case-insensitive filesystem finds
            # itself at the destination; that is the file we are moving.
            plan.old_path.exists() and destination.samefile(plan.old_path)
        ):
            return f"rename target already exists: {destination}"
        if Comic.objects.filter(path=str(destination)).exclude(pk=plan.pk).exists():
            return f"another comic already holds {destination}"
        return ""

    @classmethod
    def _claim_conflict(
        cls, plan: RenamePlan, claimed: dict[Path, int], comic_paths: dict[int, Path]
    ) -> str:
        """Return why this plan's destinations are unavailable, or ""."""
        for destination in (plan.target, plan.final_path):
            if reason := cls._destination_conflict(plan, destination, claimed):
                return reason
        # A path another comic in this batch is renaming *away* from is
        # only free once that rename runs, which it may not.
        for other_pk, other_path in comic_paths.items():
            if other_pk != plan.pk and other_path in (plan.target, plan.final_path):
                return f"{plan.target} is another comic's current path"
        return ""

    def _rename_first(
        self,
        task: BulkTagWriteTask,
        comic_paths: dict[int, Path],
        lib_of: dict[int, int],
    ) -> dict[int, Path]:
        """Rename archives to their scheme names and move the rows with them."""
        if not task.rename:
            return {}
        plans = self._plan_renames(task, comic_paths)
        renamed: dict[int, Path] = {}
        moves: defaultdict[int, dict[int, tuple[str, str]]] = defaultdict(dict)
        for plan in plans:
            if plan.target == plan.old_path:
                continue
            try:
                plan.old_path.rename(plan.target)
            except OSError as exc:
                self._report_error(plan.old_path, f"rename failed: {exc}")
                continue
            renamed[plan.pk] = plan.target
            moves[lib_of[plan.pk]][plan.pk] = (
                str(plan.old_path),
                str(plan.target),
            )
        for library_id, library_moves in moves.items():
            for pk in self._apply_moves_inline(library_id, library_moves):
                # The database refused the move, so put the file back
                # rather than leave the row pointing at a path that no
                # longer exists.
                self._revert_rename(pk, library_moves[pk])
                renamed.pop(pk, None)
        return renamed

    def _revert_rename(self, pk: int, move: tuple[str, str]) -> None:
        """Undo a disk rename whose database move did not take."""
        src, dest = move
        old_path = Path(src)
        new_path = Path(dest)
        try:
            if new_path.exists() and not old_path.exists():
                new_path.rename(old_path)
        except OSError as exc:
            self.log.warning(f"Could not undo rename of {dest}: {exc}")
        self._report_error(new_path, f"rename reverted; database move failed (pk {pk})")

    def _rename_kept_conversions(
        self,
        task: BulkTagWriteTask,
        current_paths: dict[int, Path],
        written_paths: dict[int, Path],
        converted_paths: dict[int, Path],
    ) -> dict[int, Path]:
        """Give the new CBZ of a kept-original conversion its scheme name."""
        if not task.rename or task.delete_original:
            return {}
        config = build_predict_config(task.delete_keys, task.mode)
        post_renamed: dict[int, Path] = {}
        for pk, written_path in written_paths.items():
            if pk in converted_paths or written_path == current_paths[pk]:
                continue
            try:
                name = predict_name(written_path, None, config)
                if not name:
                    continue
                target = written_path.parent / name
                if target == written_path or target.exists():
                    continue
                written_path.rename(target)
            except Exception as exc:
                self._report_error(written_path, f"rename failed: {exc}")
                continue
            post_renamed[pk] = target
        return post_renamed

    def _report_error(self, path: Path, reason: str) -> None:
        """Surface a per-file failure to admins (badge + Tagging panel)."""
        self.log.warning(f"Tag write: {reason} for {path}")
        add_tag_write_error(str(path), reason)
        self.librarian_queue.put(TAG_WRITE_ERRORS_CHANGED_TASK)

    def _apply_moves_inline(
        self, library_id: int, moves: dict[int, tuple[str, str]]
    ) -> set[int]:
        """
        Apply path moves to the database now, and report which didn't take.

        Runs the importer's own move phase rather than a hand-rolled path
        update: it drops moves onto occupied destinations, keeps the stored
        stat a rename doesn't change, and re-parents the row. Constructing
        the importer costs one query. Its ``apply``/``finish`` are never
        called — ``finish`` would end this batch's live progress status.

        Failures are read back from the database rather than inferred from
        the move phase's count, which reports nothing about *which* comic
        it dropped and can come back zero after the rows were already
        updated.
        """
        if not moves:
            return set()
        start_time = now()
        import_task = ImportTask(
            library_id=library_id,
            files_moved=dict(moves.values()),
        )
        importer = ComicImporter(
            import_task,
            self.log,
            self.librarian_queue,
            self.db_write_lock,
            self.abort_event,
        )
        try:
            importer.bulk_comics_moved()
        except Exception:
            self.log.exception(f"Applying tag write moves in library {library_id}")
        landed = dict(Comic.objects.filter(pk__in=moves).values_list("pk", "path"))
        failed = {pk for pk, (_, dest) in moves.items() if landed.get(pk) != dest}
        TimestampUpdater(
            self.log, self.librarian_queue, self.db_write_lock
        ).update_library_collections(importer.library, start_time, {})
        # The browser's page-mtime cache would otherwise serve the old
        # paths for its TTL.
        cache.clear()
        self.librarian_queue.put(LIBRARY_CHANGED_TASK)
        return failed

    def _sync_conversions(
        self,
        task: BulkTagWriteTask,
        current_paths: dict[int, Path],
        written_paths: dict[int, Path],
        lib_of: dict[int, int],
    ) -> dict[int, Path]:
        """
        Move rows onto the CBZ a conversion produced, and report which moved.

        A repacked archive is a new file at a new path, and the original is
        gone under ``delete_original`` — neither scanner can pair that into
        a move, so codex has to state it. With the original kept, the row
        stays on it and the CBZ is a separate new file.
        """
        if not task.delete_original:
            return {}
        moves: defaultdict[int, dict[int, tuple[str, str]]] = defaultdict(dict)
        converted: dict[int, Path] = {}
        for pk, written_path in written_paths.items():
            source = current_paths[pk]
            if written_path == source:
                continue
            moves[lib_of[pk]][pk] = (str(source), str(written_path))
            converted[pk] = written_path
        for library_id, library_moves in moves.items():
            for pk in self._apply_moves_inline(library_id, library_moves):
                self.log.warning(
                    f"Tag write: conversion move failed for {library_moves[pk][1]}"
                )
                converted.pop(pk, None)
        return converted

    def _enqueue_rereads(
        self,
        current_paths: dict[int, Path],
        written_paths: dict[int, Path],
        converted_paths: dict[int, Path],
        post_renamed: dict[int, Path],
        lib_of: dict[int, int],
    ) -> None:
        """
        Ask the importer to re-read the metadata codex just wrote.

        Every move is already applied, so these tasks only name paths the
        database holds: a scan that beats them to the queue reconciles
        against rows that are already correct. Watched libraries would
        eventually re-read from the watcher's own modify event, but only
        with the import-metadata flag on, so the re-read is requested
        either way.
        """
        modified: defaultdict[int, set[str]] = defaultdict(set)
        created: defaultdict[int, set[str]] = defaultdict(set)
        for pk, written_path in written_paths.items():
            library_id = lib_of[pk]
            if pk in converted_paths:
                modified[library_id].add(str(converted_paths[pk]))
            elif written_path != current_paths[pk]:
                # A kept original's new CBZ is a file the database has
                # never seen.
                created[library_id].add(str(post_renamed.get(pk, written_path)))
            else:
                modified[library_id].add(str(written_path))
        # A rename with no write changed no metadata, so nothing to re-read.
        for library_id in modified.keys() | created.keys():
            import_task = ImportTask(
                library_id=library_id,
                files_modified=frozenset(modified.get(library_id, ())),
                files_created=frozenset(created.get(library_id, ())),
                force_import_metadata=True,
                check_metadata_mtime=False,
            )
            self.librarian_queue.put(import_task)
