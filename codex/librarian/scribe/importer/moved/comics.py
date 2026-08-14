"""Bulk import and move comics."""

from collections.abc import Mapping
from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.scribe.importer.const import (
    CREATE_FKS,
    FOLDERS_FIELD_NAME,
    MOVED_BULK_COMIC_UPDATE_FIELDS,
    PARENT_FOLDER_FIELD_NAME,
    PATH_FIELD_NAME,
)
from codex.librarian.scribe.importer.read import ReadMetadataImporter
from codex.librarian.scribe.importer.statii.create import ImporterCreateTagsStatus
from codex.librarian.scribe.importer.statii.moved import ImporterMoveComicsStatus
from codex.librarian.scribe.importer.statii.query import ImporterQueryMissingTagsStatus
from codex.models import Comic, CustomCover, Folder


class MovedComicsImporter(ReadMetadataImporter):
    """Methods for moving comics and folders."""

    def _remove_file_move_collisions(
        self,
        model: type[Comic] | type[CustomCover],
        moves: Mapping[str, str],
        item_name: str,
    ) -> dict[str, str]:
        """
        Remove moves whose destination path is already claimed.

        The poller and the watcher both infer moves from inode matches
        without checking that the destination is free in the database.
        A destination that already belongs to another row would violate
        the ``(library, path)`` unique constraint inside the upcoming
        ``bulk_update``, and that exception aborted the entire import,
        leaving the delete phase unreachable so the same task crashed
        again on every subsequent scan.

        Two claims are possible. An existing row may sit at the
        destination already (a duplicate file landing on a tracked
        path, or an overwrite-rename), or two sources in this batch may
        resolve to the same destination, which ``files_moved`` can
        express because it is a plain dict rather than the bidict
        folder moves use. Drop both, keeping the lowest sorted source
        for a duplicated destination so the choice is deterministic.

        Skipping converges rather than stranding anything. The
        destination row's stat is refreshed by the modified reimport or
        by the poller's stale stat pass, so the next scan sees two rows
        sharing an inode, suppresses the bogus move as ambiguous, and
        the stale source falls through to the delete phase. Libraries
        that only run the watcher wait for their next poll instead. A
        source and destination that swap paths drop both moves and
        reconcile as content changes in place, which a single
        ``bulk_update`` could not express under SQLite anyway.

        This is normal reconciliation, not a fault. Log at INFO with a
        count and at DEBUG with the paths, matching the folder guard.
        """
        if not moves:
            return {}
        occupied_paths = frozenset(
            model.objects.filter(
                library=self.library, path__in=frozenset(moves.values())
            ).values_list(PATH_FIELD_NAME, flat=True)
        )
        kept_moves: dict[str, str] = {}
        claimed_paths: set[str] = set()
        skipped_paths: list[str] = []
        for src_path in sorted(moves):
            dest_path = moves[src_path]
            if dest_path in occupied_paths or dest_path in claimed_paths:
                skipped_paths.append(src_path)
            else:
                kept_moves[src_path] = dest_path
                claimed_paths.add(dest_path)
        if skipped_paths:
            count = len(skipped_paths)
            plural = "s" if count != 1 else ""
            msg = (
                f"Resolved {count} phantom {item_name} move{plural} by skipping "
                "the rename and leaving the destinations in place."
            )
            self.log.info(msg)
            self.log.debug(f"Skipped {item_name} move sources: {skipped_paths}")
        return kept_moves

    def _bulk_comics_moved_ensure_folders(self) -> None:
        """Ensure folders we're moving to exist."""
        dest_comic_paths = self.task.files_moved.values()
        dest_comic_paths = self.get_all_library_relative_paths(dest_comic_paths)
        num_dest_comic_paths = len(dest_comic_paths)
        if not num_dest_comic_paths:
            return
        # Not sending statues to the controller for now.
        status = ImporterQueryMissingTagsStatus()
        if CREATE_FKS not in self.metadata:
            self.metadata[CREATE_FKS] = {}
        proposed_values_map = {path: set() for path in dest_comic_paths}
        self.query_missing_models(
            Folder,
            proposed_values_map,
            status,
        )
        create_folder_paths = self.metadata[CREATE_FKS].pop(Folder, {})
        count = len(create_folder_paths)
        if not count:
            return
        status = ImporterCreateTagsStatus(0, count)
        self.log.debug(
            "Creating {count} folders for {num_dest_comic_paths} moved comics."
        )
        self.bulk_folders_create(create_folder_paths, status)
        self.status_controller.finish(status)

    def _prepare_moved_comic(
        self,
        comic,
        folder_pk_by_path: dict[str, int],
        folder_m2m_links: dict,
        updated_comics: list,
        del_folder_rows: list,
    ) -> None:
        """Prepare one comic for bulk update."""
        try:
            new_path_str = self.task.files_moved[comic.path]
            old_folder_pks = frozenset(folder.pk for folder in comic.folders.all())
            comic.path = new_path_str
            new_path = Path(new_path_str)
            # Library-scoped pk lookup via the prebuilt map. Replaces a
            # per-comic ``Folder.objects.get(path=...)``, and tightens the
            # search to this library so a parent_folder can no longer
            # resolve to another library sharing the same on-disk path.
            # Bracket access raises ``KeyError`` on a genuinely missing
            # parent — same outer behavior as the prior ``DoesNotExist``
            # (caught by the broad except below).
            comic.parent_folder_id = folder_pk_by_path[str(new_path.parent)]
            comic.updated_at = Now()
            comic.presave()
            # Missing ancestors silently absent from the set, matching
            # the prior ``filter(path__in=...)`` behavior.
            new_folder_pks = frozenset(
                pk
                for parent in new_path.parents
                if (pk := folder_pk_by_path.get(str(parent))) is not None
            )
            folder_m2m_links[comic.pk] = new_folder_pks
            updated_comics.append(comic)
            if del_folder_pks := old_folder_pks - new_folder_pks:
                del_folder_rows.extend((comic.pk, pk) for pk in del_folder_pks)
        except Exception:
            self.log.exception(f"moving {comic.path}")

    def _bulk_comics_move_prepare(self) -> tuple[list, dict, dict]:
        """Prepare Update Comics."""
        # _bulk_comics_moved_ensure_folders has already created any
        # destination folders that were missing. One values_list pass
        # here builds a path->pk map covering every parent path the
        # per-comic loop below can possibly need; replaces the prior
        # 2-SELECTs-per-moved-comic shape.
        folder_pk_by_path: dict[str, int] = dict(
            Folder.objects.filter(library=self.library).values_list(
                PATH_FIELD_NAME, "pk"
            )
        )

        comics = (
            Comic.objects.prefetch_related(FOLDERS_FIELD_NAME)
            .filter(library=self.library, path__in=self.task.files_moved.keys())
            .only(PATH_FIELD_NAME, PARENT_FOLDER_FIELD_NAME, FOLDERS_FIELD_NAME)
        )

        folder_m2m_links: dict = {}
        updated_comics: list = []
        del_folder_rows: list = []
        for comic in comics:
            self._prepare_moved_comic(
                comic,
                folder_pk_by_path,
                folder_m2m_links,
                updated_comics,
                del_folder_rows,
            )
        self.task.files_moved = {}
        self.log.debug(f"Prepared {len(updated_comics)} for move...")
        del_rows_map = {}
        if del_folder_rows:
            del_rows_map[FOLDERS_FIELD_NAME] = del_folder_rows
        return updated_comics, folder_m2m_links, del_rows_map

    def bulk_comics_moved(self) -> int:
        """Move comics."""
        count = 0
        num_files_moved = len(self.task.files_moved)
        status = ImporterMoveComicsStatus(0, num_files_moved)
        try:
            if not num_files_moved:
                return count
            self.status_controller.start(status)

            # Drop moves onto claimed paths before creating any folders
            # for destinations that will not be used.
            self.task.files_moved = self._remove_file_move_collisions(
                Comic, self.task.files_moved, "comic"
            )

            # Prepare
            self._bulk_comics_moved_ensure_folders()
            updated_comics, folder_m2m_links, del_rows_map = (
                self._bulk_comics_move_prepare()
            )

            # Update comics
            # Potentially could just add these to the right structures and do it later during create and link.
            Comic.objects.bulk_update(updated_comics, MOVED_BULK_COMIC_UPDATE_FIELDS)
            if del_rows_map:
                self.delete_m2m_field(FOLDERS_FIELD_NAME, del_rows_map, status)
            if folder_m2m_links:
                self.link_comic_m2m_field(FOLDERS_FIELD_NAME, folder_m2m_links, status)

            count = len(updated_comics)
        except Exception:
            # Broad by intent. A failed move phase must degrade to a
            # skipped phase that the next scan reconciles, never abort
            # the import, which left the delete phase unreachable and
            # the same task crashing on every scan.
            self.log.exception(f"Moving {num_files_moved} comics")
        finally:
            self.status_controller.finish(status)
        return count
