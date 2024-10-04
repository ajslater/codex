"""Bulk import and move comics and folders."""

from pathlib import Path

from bidict import bidict
from django.db.models.functions import Now

from codex.librarian.importer.aggregate import AggregateMetadataImporter
from codex.librarian.importer.const import (
    BULK_UPDATE_FOLDER_MODIFIED_FIELDS,
    CLASS_CUSTOM_COVER_GROUP_MAP,
    CUSTOM_COVER_UPDATE_FIELDS,
    FOLDERS_FIELD,
    LINK_COVER_PKS,
    MOVED_BULK_COMIC_UPDATE_FIELDS,
    MOVED_BULK_FOLDER_UPDATE_FIELDS,
    PARENT_FOLDER,
)
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import Comic, CustomCover, Folder
from codex.status import Status


class MovedImporter(AggregateMetadataImporter):
    """Methods for moving comics and folders."""

    def _bulk_comics_moved_ensure_folders(self):
        """Ensure folders we're moving to exist."""
        dest_comic_paths = self.task.files_moved.values()
        if not dest_comic_paths:
            return
        # Not sending statues to the controller for now.
        status = Status(ImportStatusTypes.QUERY_MISSING_FKS)
        create_folder_paths = self.query_missing_folder_paths(dest_comic_paths, status)
        if not create_folder_paths:
            return
        status = Status(ImportStatusTypes.CREATE_FKS, 0, len(create_folder_paths))
        self.log.debug(
            "Creating {len(create_folder_paths)} folders for {len(dest_comic_paths)} moved comics."
        )
        self.bulk_folders_create(create_folder_paths, status)

    def _prepare_moved_comic(self, comic, folder_m2m_links, updated_comics):
        """Prepare one comic for bulk update."""
        try:
            new_path = self.task.files_moved[comic.path]
            comic.path = new_path
            new_path = Path(new_path)
            comic.parent_folder = Folder.objects.get(  # type: ignore
                path=new_path.parent
            )
            comic.updated_at = Now()
            comic.presave()
            folder_m2m_links[comic.pk] = Folder.objects.filter(
                path__in=new_path.parents
            ).values_list("pk", flat=True)
            updated_comics.append(comic)
        except Exception:
            self.log.exception(f"moving {comic.path}")

    def _bulk_comics_move_prepare(self):
        """Prepare Update Comics."""
        comics = Comic.objects.filter(
            library=self.library, path__in=self.task.files_moved.keys()
        ).only("pk", "path", PARENT_FOLDER, FOLDERS_FIELD)

        folder_m2m_links = {}
        updated_comics = []
        for comic in comics.iterator():
            self._prepare_moved_comic(comic, folder_m2m_links, updated_comics)
        self.task.files_moved = {}
        self.log.debug(f"Prepared {len(updated_comics)} for move...")
        return updated_comics, folder_m2m_links

    def _bulk_comics_moved(self):
        """Move comcis."""
        num_files_moved = len(self.task.files_moved)
        if not num_files_moved:
            return
        status = Status(ImportStatusTypes.FILES_MOVED, 0, num_files_moved)
        self.status_controller.start(status)

        # Prepare
        self._bulk_comics_moved_ensure_folders()
        updated_comics, folder_m2m_links = self._bulk_comics_move_prepare()

        # Update comics
        Comic.objects.bulk_update(updated_comics, MOVED_BULK_COMIC_UPDATE_FIELDS)
        if folder_m2m_links:
            self.bulk_fix_comic_m2m_field(FOLDERS_FIELD, folder_m2m_links, status)

        count = len(updated_comics)
        if count:
            self.log.info(f"Moved {count} comics.")

        self.changed += count
        self.status_controller.finish(status)

    def _bulk_covers_moved_prepare(self, status):
        """Create an update map for bulk update."""
        covers = CustomCover.objects.filter(
            library=self.library, path__in=self.task.covers_moved.keys()
        ).only("pk", "path")

        if status:
            status.total = covers.count()

        moved_covers = []
        unlink_pks = set()
        for cover in covers.iterator():
            try:
                new_path = self.task.covers_moved[cover.path]
                cover.path = new_path
                new_path = Path(new_path)
                cover.updated_at = Now()
                cover.presave()
                moved_covers.append(cover)
                unlink_pks.add(cover.pk)
            except Exception:
                self.log.exception(f"moving {cover.path}")
        return moved_covers, unlink_pks

    def _bulk_covers_moved_unlink(self, unlink_pks):
        """Unlink moved covers because they could have moved between group dirs."""
        if not unlink_pks:
            return
        self.log.debug(f"Unlinking {len(unlink_pks)} moved custom covers.")
        for model in CLASS_CUSTOM_COVER_GROUP_MAP:
            groups = model.objects.filter(custom_cover__in=unlink_pks)
            unlink_groups = []
            for group in groups:
                group.custom_cover = None
                unlink_groups.append(group)
            if unlink_groups:
                model.objects.bulk_update(unlink_groups, ["custom_cover"])
                self.log.debug(
                    f"Unlinked {len(unlink_groups)} {model.__name__} moved custom covers."
                )

        self._remove_covers(unlink_pks, custom=True)  # type: ignore

    def _bulk_covers_moved(self, status=None):
        """Move covers."""
        num_covers_moved = len(self.task.covers_moved)
        if not num_covers_moved:
            return
        status = Status(ImportStatusTypes.COVERS_MOVED, None, num_covers_moved)
        self.status_controller.start(status)

        moved_covers, unlink_pks = self._bulk_covers_moved_prepare(status)
        if LINK_COVER_PKS not in self.metadata:
            self.metadata[LINK_COVER_PKS] = set()
        self.metadata[LINK_COVER_PKS].update(unlink_pks)
        if moved_covers:
            CustomCover.objects.bulk_update(moved_covers, CUSTOM_COVER_UPDATE_FIELDS)

        self._bulk_covers_moved_unlink(unlink_pks)

        count = len(moved_covers)
        if count:
            self.log.info(f"Moved {count} custom covers.")

        self.changed += count
        self.status_controller.finish(status)

    def _bulk_move_folders(
        self,
        src_folder_paths_with_existing_dest_parents,
        dest_parent_folders_map,
        dirs_moved: bidict[str, str],
        status,
    ):
        """Bulk move folders."""
        # Move collisions removed before this
        folders_to_move = (
            Folder.objects.filter(
                library=self.library,
                path__in=src_folder_paths_with_existing_dest_parents,
            )
            .only(*MOVED_BULK_FOLDER_UPDATE_FIELDS)
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

        # delete_folders = Folder.objects.filter(library=self.library, path__in=new_paths)

        update_folders = sorted(update_folders, key=lambda x: len(Path(x.path).parts))

        Folder.objects.bulk_update(update_folders, MOVED_BULK_FOLDER_UPDATE_FIELDS)
        count = len(update_folders)
        if count:
            self.log.info(f"Moved {count} folders.")
        self.changed += count
        status.add_complete(count)
        self.status_controller.update(status, notify=False)

    def _bulk_move_folders_under_existing_parents(
        self, dest_parent_folder_paths_map, dirs_moved: bidict, status
    ):
        """Move folders under existing folders."""
        while True:
            # Get existing parent folders
            # dest_parent_paths = tuple(str(path) for path in dest_parent_folder_paths_map)
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
                return
            src_folder_paths_with_existing_dest_parents = sorted(
                src_folder_paths_with_existing_dest_parents
            )
            self.log.debug(
                f"Moving folders under existing parents: {src_folder_paths_with_existing_dest_parents}"
            )

            self._bulk_move_folders(
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
        dirs_moved = bidict(self.task.dirs_moved)

        self._remove_move_collisions(dirs_moved)

        dest_paths = sorted(set(dirs_moved.values()))
        dest_parent_folder_paths_map = {}
        for dest_path in dest_paths:
            parent = str(Path(dest_path).parent)
            if parent not in dest_parent_folder_paths_map:
                dest_parent_folder_paths_map[parent] = set()
            dest_parent_folder_paths_map[parent].add(dest_path)

        create_status = Status(ImportStatusTypes.CREATE_FKS)
        layer = 1
        while True:
            self._bulk_move_folders_under_existing_parents(
                dest_parent_folder_paths_map, dirs_moved, status
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
            self.bulk_folders_create(create_folder_paths_one_layer, create_status)
            layer += 1

    def bulk_folders_moved(self):
        """Move folders in the database instead of recreating them."""
        num_dirs_moved = len(self.task.dirs_moved)
        if not num_dirs_moved:
            return
        status = Status(ImportStatusTypes.DIRS_MOVED, None, num_dirs_moved)
        self.status_controller.start(status)

        self._bulk_move_folders_and_create_parents(status)
        self.task.dirs_moved = {}

        self.status_controller.finish(status)

    def _bulk_folders_modified(self):
        """Update folders stat and nothing else."""
        num_dirs_modified = len(self.task.dirs_modified)
        if not num_dirs_modified:
            return
        status = Status(ImportStatusTypes.DIRS_MODIFIED, None, num_dirs_modified)
        self.status_controller.start(status)

        folders = Folder.objects.filter(
            library=self.library, path__in=self.task.dirs_modified
        ).only("stat", "updated_at")
        self.task.dirs_modified = frozenset()
        update_folders = []
        for folder in folders.iterator():
            if Path(folder.path).exists():
                folder.updated_at = Now()
                folder.presave()
                update_folders.append(folder)
        Folder.objects.bulk_update(
            update_folders, fields=BULK_UPDATE_FOLDER_MODIFIED_FIELDS
        )
        count = len(update_folders)
        if count:
            self.log.info(f"Modified {count} folders")
        self.changed += count
        self.status_controller.finish(status)

    def move_and_modify_dirs(self):
        """Move files and dirs and modify dirs."""
        # It would be nice to move folders instead of recreating them but it would require
        # an inode map from the snapshots to do correctly.
        self.bulk_folders_moved()
        self._bulk_comics_moved()
        self._bulk_covers_moved()
        self._bulk_folders_modified()
