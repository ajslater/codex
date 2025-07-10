"""Bulk import and move comics and folders."""

from pathlib import Path

from bidict import bidict, frozenbidict
from django.db.models.functions import Now

from codex.librarian.scribe.importer.const import (
    BULK_UPDATE_FOLDER_FIELDS,
)
from codex.librarian.scribe.importer.moved.covers import MovedCoversImporter
from codex.librarian.scribe.importer.statii.create import ImporterCreateTagsStatus
from codex.librarian.scribe.importer.statii.moved import ImporterMoveFoldersStatus
from codex.librarian.status import Status
from codex.models import Folder


class MovedFoldersImporter(MovedCoversImporter):
    """Methods for moving comics and folders."""

    @staticmethod
    def _folder_sort_key(element: Folder):
        return len(Path(element.path).parts)

    def _bulk_move_folders(
        self,
        src_folder_paths_with_existing_dest_parents,
        dest_parent_folders_map,
        dirs_moved: frozenbidict[str, str],
        status: Status,
    ):
        """Bulk move folders."""
        # Move collisions removed before this
        folders_to_move = (
            Folder.objects.filter(
                library=self.library,
                path__in=src_folder_paths_with_existing_dest_parents,
            )
            .only(*BULK_UPDATE_FOLDER_FIELDS)
            .order_by("path")
        )

        new_paths = set()
        update_folders = []
        for folder in folders_to_move.iterator():
            new_path = dirs_moved[folder.path]
            new_paths.add(new_path)
            folder.name = Path(new_path).name
            folder.path = new_path
            parent_path_str = str(Path(new_path).parent)
            folder.parent_folder = dest_parent_folders_map.get(parent_path_str)
            folder.presave()
            folder.updated_at = Now()
            update_folders.append(folder)

        update_folders = sorted(update_folders, key=self._folder_sort_key)

        Folder.objects.bulk_update(update_folders, BULK_UPDATE_FOLDER_FIELDS)
        count = len(update_folders)
        level = "INFO" if count else "DEBUG"
        self.log.log(level, f"Moved {count} folders.")
        status.increment_complete(count)
        self.status_controller.update(status)
        return count

    def _bulk_move_folders_under_existing_parents(
        self, dest_parent_folder_paths_map, dirs_moved: frozenbidict[str, str], status
    ):
        """Move folders under existing folders."""
        count = 0
        while True:
            # Get existing parent folders
            dest_parent_paths = tuple(dest_parent_folder_paths_map.keys())
            extant_parent_folders = Folder.objects.filter(
                library=self.library, path__in=dest_parent_paths
            ).only("path")

            # Create a list of folders than can be moved under existing folders.
            dest_parent_folders_map = {}
            src_folder_paths_with_existing_dest_parents = []
            for extant_parent_folder in extant_parent_folders:
                dest_parent_folders_map[extant_parent_folder.path] = (
                    extant_parent_folder
                )
                if dest_folder_paths := dest_parent_folder_paths_map.pop(
                    extant_parent_folder.path, None
                ):
                    for dest_folder_path in dest_folder_paths:
                        src_path = dirs_moved.inverse[dest_folder_path]
                        src_folder_paths_with_existing_dest_parents.append(src_path)

            if not src_folder_paths_with_existing_dest_parents:
                return count
            src_folder_paths_with_existing_dest_parents = sorted(
                src_folder_paths_with_existing_dest_parents
            )
            self.log.debug(
                f"Moving folders under existing parents: {src_folder_paths_with_existing_dest_parents}"
            )

            count += self._bulk_move_folders(
                src_folder_paths_with_existing_dest_parents,
                dest_parent_folders_map,
                dirs_moved,
                status,
            )

    def _get_move_create_folders_one_layer(self, dest_parent_folder_paths_map):
        """Find the next layer of folder paths to create."""
        create_folder_paths_one_layer = set()
        library_parts_len = len(Path(self.library.path).parts)
        for parent_path_str in sorted(dest_parent_folder_paths_map.keys()):
            parts = Path(parent_path_str).parts
            # Get one layer of folders from existing layers.
            possible_create_folder_path = ""
            for index in range(library_parts_len, len(parts) + 1):
                layer_parts = parts[:index]
                possible_create_folder_path = str(Path(*layer_parts))
                if (
                    possible_create_folder_path in create_folder_paths_one_layer
                    or not Folder.objects.filter(
                        library=self.library, path=possible_create_folder_path
                    ).exists()
                ):
                    break
            else:
                possible_create_folder_path = ""
            if possible_create_folder_path:
                create_folder_paths_one_layer.add(possible_create_folder_path)

        return frozenset(create_folder_paths_one_layer)

    def _remove_move_collisions(self, dirs_moved: bidict[str, str]):
        """Remove moves that would collide with an existing Folder."""
        dest_paths = set(dirs_moved.values())
        collision_dest_paths = Folder.objects.filter(
            library=self.library, path__in=dest_paths
        ).values_list("path", flat=True)
        if not collision_dest_paths:
            return
        collision_dest_paths = sorted(set(collision_dest_paths))
        for collision_dest_path in collision_dest_paths:
            dirs_moved.inverse.pop(collision_dest_path, None)
        self.log.warning(
            f"Not moving folders to destinations that would collide with existing database folders: {collision_dest_paths}"
        )

    def _bulk_move_folders_and_create_parents(self, status):
        """Find folders that can be moved without creating parents."""
        count = 0
        dirs_moved = bidict(self.task.dirs_moved)

        self._remove_move_collisions(dirs_moved)

        dest_paths = sorted(set(dirs_moved.values()))
        dest_parent_folder_paths_map = {}
        for dest_path in dest_paths:
            parent = str(Path(dest_path).parent)
            if parent not in dest_parent_folder_paths_map:
                dest_parent_folder_paths_map[parent] = set()
            dest_parent_folder_paths_map[parent].add(dest_path)

        create_status = ImporterCreateTagsStatus()
        layer = 1
        while True:
            self._bulk_move_folders_under_existing_parents(
                dest_parent_folder_paths_map, frozenbidict(dirs_moved), status
            )

            # All folders movable without creation have moved.
            if not dest_parent_folder_paths_map:
                break
            self.log.debug(
                f"Creating intermediate folder layer {layer} to move folders."
            )
            create_folder_paths_one_layer = self._get_move_create_folders_one_layer(
                dest_parent_folder_paths_map
            )

            # Create one layer of folders
            count += self.bulk_folders_create(
                create_folder_paths_one_layer, create_status
            )
            layer += 1
        return count

    def bulk_folders_moved(self, *, mark_in_progress=False):
        """Move folders in the database instead of recreating them."""
        count = 0
        num_dirs_moved = len(self.task.dirs_moved)
        status = ImporterMoveFoldersStatus(None, num_dirs_moved)
        try:
            if not num_dirs_moved:
                return count
            if mark_in_progress:
                self.library.start_update()
            self.status_controller.start(status)

            count += self._bulk_move_folders_and_create_parents(status)
            self.task.dirs_moved = {}
        finally:
            self.status_controller.finish(status)
            if mark_in_progress:
                self.library.end_update()
        return count
